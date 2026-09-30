package main

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"os"
)

type Command struct {
	Type         string `json:"type"`
	Direction    string `json:"direction,omitempty"`
	Milliseconds int    `json:"milliseconds,omitempty"`
}

type Response struct {
	Accepted bool   `json:"accepted"`
	Reason   string `json:"reason,omitempty"`
	State    Game   `json:"state"`
}

func run(input io.Reader, output io.Writer) error {
	game := newGame()
	decoder := json.NewDecoder(bufio.NewReader(input))
	encoder := json.NewEncoder(output)
	encoder.SetEscapeHTML(false)
	for {
		var command Command
		if err := decoder.Decode(&command); err != nil {
			if err == io.EOF {
				return nil
			}
			return fmt.Errorf("decode command: %w", err)
		}
		accepted, reason := game.apply(command)
		if err := encoder.Encode(Response{Accepted: accepted, Reason: reason, State: game}); err != nil {
			return fmt.Errorf("encode response: %w", err)
		}
	}
}

func main() {
	if err := run(os.Stdin, os.Stdout); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
