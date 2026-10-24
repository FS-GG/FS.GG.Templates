package main

import (
	"bytes"
	"os/exec"
	"path/filepath"
	"testing"
)

func TestLiteralDomain(t *testing.T) {
	if got := polyglot_greet("$(literal);& with spaces"); got != "hello $(literal);& with spaces" {
		t.Fatal(got)
	}
}

func TestActualCLI(t *testing.T) {
	binary := filepath.Join(t.TempDir(), "product-cli")
	if output, err := exec.Command("go", "build", "-trimpath", "-o", binary, ".").CombinedOutput(); err != nil {
		t.Fatalf("build: %s %v", output, err)
	}
	output, err := exec.Command(binary, "hello", "$(literal);& with spaces").Output()
	if err != nil || string(output) != "hello $(literal);& with spaces\n" {
		t.Fatalf("%q %v", output, err)
	}
	cmd := exec.Command(binary, "--fail")
	var stderr bytes.Buffer
	cmd.Stderr = &stderr
	err = cmd.Run()
	exit, ok := err.(*exec.ExitError)
	if !ok || exit.ExitCode() != 2 || stderr.String() != "requested failure\n" {
		t.Fatalf("failure: %q %v", stderr.String(), err)
	}
}
