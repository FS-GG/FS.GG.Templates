package main

import (
	"fmt"
	"os"
)

func polyglot_greet(name string) string { return "hello " + name }
func main() {
	args := os.Args[1:]
	if len(args) > 0 && args[0] != "hello" {
		fmt.Fprintln(os.Stderr, "requested failure")
		os.Exit(2)
	}
	name := "world"
	if len(args) > 1 {
		name = args[1]
	}
	fmt.Println(polyglot_greet(name))
}
