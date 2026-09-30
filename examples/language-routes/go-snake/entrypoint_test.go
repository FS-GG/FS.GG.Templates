package main

import (
	"bufio"
	"encoding/json"
	"io"
	"os/exec"
	"path/filepath"
	"testing"
)

type builtSnake struct {
	command *exec.Cmd
	input   io.WriteCloser
	output  *bufio.Reader
}

func startBuiltSnake(t *testing.T) *builtSnake {
	t.Helper()
	binary := filepath.Join(t.TempDir(), "go-snake")
	build := exec.Command("go", "build", "-trimpath", "-o", binary, ".")
	build.Env = append(build.Environ(), "GOTOOLCHAIN=local")
	if output, err := build.CombinedOutput(); err != nil {
		t.Fatalf("build actual entrypoint: %v\n%s", err, output)
	}
	command := exec.Command(binary)
	input, err := command.StdinPipe()
	if err != nil {
		t.Fatal(err)
	}
	stdout, err := command.StdoutPipe()
	if err != nil {
		t.Fatal(err)
	}
	if err := command.Start(); err != nil {
		t.Fatal(err)
	}
	process := &builtSnake{command: command, input: input, output: bufio.NewReader(stdout)}
	t.Cleanup(func() {
		_ = process.input.Close()
		_ = process.command.Wait()
	})
	return process
}

func (process *builtSnake) send(t *testing.T, command Command) Response {
	t.Helper()
	bytes, err := json.Marshal(command)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := process.input.Write(append(bytes, '\n')); err != nil {
		t.Fatal(err)
	}
	line, err := process.output.ReadBytes('\n')
	if err != nil {
		t.Fatal(err)
	}
	var response Response
	if err := json.Unmarshal(line, &response); err != nil {
		t.Fatalf("decode response %q: %v", line, err)
	}
	return response
}

func expectAccepted(t *testing.T, response Response) Game {
	t.Helper()
	if !response.Accepted {
		t.Fatalf("command refused: %s", response.Reason)
	}
	return response.State
}

func TestBuiltEntrypointPlayerJourney(t *testing.T) {
	process := startBuiltSnake(t)
	initial := expectAccepted(t, process.send(t, Command{Type: "state"}))
	if initial.Status != "ready" || initial.Body[0] != (Point{X: 16, Y: 9}) || initial.Food == nil || *initial.Food != (Point{X: 20, Y: 9}) {
		t.Fatalf("public initial state is wrong: %+v", initial)
	}
	expectAccepted(t, process.send(t, Command{Type: "start"}))
	if refusal := process.send(t, Command{Type: "direction", Direction: "left"}); refusal.Accepted || refusal.Reason != "turn-reversal-refused" {
		t.Fatalf("public reversal was not refused: %+v", refusal)
	}
	grown := expectAccepted(t, process.send(t, Command{Type: "advance", Milliseconds: 720}))
	if grown.Score != 10 || len(grown.Body) != 4 || grown.Body[0] != (Point{X: 20, Y: 9}) {
		t.Fatalf("public growth failed: %+v", grown)
	}
	expectAccepted(t, process.send(t, Command{Type: "pause"}))
	if advanced := process.send(t, Command{Type: "advance", Milliseconds: 1_000}); advanced.Accepted || advanced.State.Body[0] != grown.Body[0] {
		t.Fatalf("paused public clock was not fenced: %+v", advanced)
	}
	expectAccepted(t, process.send(t, Command{Type: "resume"}))
	lost := expectAccepted(t, process.send(t, Command{Type: "advance", Milliseconds: 5_000}))
	if lost.Status != "lost" {
		t.Fatalf("public wall collision did not terminate: %+v", lost)
	}
	if terminal := process.send(t, Command{Type: "direction", Direction: "up"}); terminal.Accepted {
		t.Fatalf("terminal public input was accepted: %+v", terminal)
	}
	restarted := expectAccepted(t, process.send(t, Command{Type: "restart"}))
	if restarted.Status != "ready" || restarted.Score != 0 || restarted.Body[0] != initial.Body[0] || restarted.Food == nil || *restarted.Food != *initial.Food {
		t.Fatalf("public restart was not deterministic: %+v", restarted)
	}
}
