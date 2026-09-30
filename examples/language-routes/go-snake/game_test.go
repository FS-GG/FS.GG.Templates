package main

import (
	"reflect"
	"testing"
)

func mustApply(t *testing.T, game *Game, command Command) {
	t.Helper()
	if accepted, reason := game.apply(command); !accepted {
		t.Fatalf("command %+v refused: %s", command, reason)
	}
}

func TestDeterministicInitialStateGrowthAndRestart(t *testing.T) {
	game := newGame()
	if game.Status != "ready" || game.Score != 0 || game.TickMS != 180 {
		t.Fatalf("unexpected initial state: %+v", game)
	}
	if game.Food == nil || *game.Food != (Point{X: 20, Y: 9}) {
		t.Fatalf("unexpected deterministic food: %+v", game.Food)
	}
	initial := newGame()
	mustApply(t, &game, Command{Type: "start"})
	mustApply(t, &game, Command{Type: "advance", Milliseconds: 720})
	if game.Score != 10 || len(game.Body) != 4 || game.TickMS != 174 {
		t.Fatalf("growth contract failed: %+v", game)
	}
	mustApply(t, &game, Command{Type: "restart"})
	if !reflect.DeepEqual(game, initial) {
		t.Fatalf("restart mismatch\n got: %+v\nwant: %+v", game, initial)
	}
}

func TestLegalTurnQueueAndReversalRefusal(t *testing.T) {
	game := newGame()
	mustApply(t, &game, Command{Type: "start"})
	if accepted, reason := game.apply(Command{Type: "direction", Direction: "left"}); accepted || reason != "turn-reversal-refused" {
		t.Fatalf("direct reversal was not refused: accepted=%v reason=%q", accepted, reason)
	}
	mustApply(t, &game, Command{Type: "direction", Direction: "down"})
	if accepted, reason := game.apply(Command{Type: "direction", Direction: "up"}); accepted || reason != "turn-reversal-refused" {
		t.Fatalf("queued reversal was not refused: accepted=%v reason=%q", accepted, reason)
	}
	mustApply(t, &game, Command{Type: "direction", Direction: "left"})
	if accepted, reason := game.apply(Command{Type: "direction", Direction: "down"}); accepted || reason != "turn-queue-full" {
		t.Fatalf("queue overflow was not refused: accepted=%v reason=%q", accepted, reason)
	}
	mustApply(t, &game, Command{Type: "advance", Milliseconds: 180})
	if game.Body[0] != (Point{X: 16, Y: 10}) {
		t.Fatalf("first buffered turn was not applied: %+v", game.Body[0])
	}
	mustApply(t, &game, Command{Type: "advance", Milliseconds: 180})
	if game.Body[0] != (Point{X: 15, Y: 10}) {
		t.Fatalf("second buffered turn was not applied: %+v", game.Body[0])
	}
}

func TestPauseResumeAndTerminalRefusal(t *testing.T) {
	game := newGame()
	mustApply(t, &game, Command{Type: "start"})
	mustApply(t, &game, Command{Type: "advance", Milliseconds: 360})
	mustApply(t, &game, Command{Type: "pause"})
	paused := append([]Point(nil), game.Body...)
	if accepted, reason := game.apply(Command{Type: "advance", Milliseconds: 5_000}); accepted || reason != "game-not-running" {
		t.Fatalf("paused clock advance was not refused: accepted=%v reason=%q", accepted, reason)
	}
	if !reflect.DeepEqual(game.Body, paused) {
		t.Fatal("paused game moved")
	}
	mustApply(t, &game, Command{Type: "resume"})
	mustApply(t, &game, Command{Type: "advance", Milliseconds: 180})
	if game.Body[0] != (Point{X: 19, Y: 9}) {
		t.Fatalf("resume did not continue: %+v", game.Body[0])
	}

	game.Body = []Point{{X: 31, Y: 3}, {X: 30, Y: 3}, {X: 29, Y: 3}}
	game.Direction = "right"
	food := Point{X: 0, Y: 0}
	game.Food = &food
	mustApply(t, &game, Command{Type: "advance", Milliseconds: game.TickMS})
	if game.Status != "lost" {
		t.Fatalf("wall collision did not lose: %+v", game)
	}
	for _, command := range []Command{{Type: "advance", Milliseconds: 180}, {Type: "direction", Direction: "up"}, {Type: "pause"}, {Type: "start"}} {
		if accepted, _ := game.apply(command); accepted {
			t.Fatalf("terminal command was accepted: %+v", command)
		}
	}
}

func TestBodyCollisionVacatingTailAndFullBoard(t *testing.T) {
	bodyCollision := Game{
		Board: Board{Width: 10, Height: 10}, Status: "running",
		Body:      []Point{{X: 2, Y: 1}, {X: 2, Y: 2}, {X: 1, Y: 2}, {X: 1, Y: 1}, {X: 1, Y: 0}},
		Direction: "left", Turns: []string{}, Food: &Point{X: 8, Y: 8}, Seed: 1, TickMS: 180,
	}
	bodyCollision.tick()
	if bodyCollision.Status != "lost" {
		t.Fatalf("body collision did not lose: %+v", bodyCollision)
	}

	vacatingTail := Game{
		Board: Board{Width: 10, Height: 10}, Status: "running",
		Body:      []Point{{X: 1, Y: 1}, {X: 1, Y: 2}, {X: 2, Y: 2}, {X: 2, Y: 1}},
		Direction: "right", Turns: []string{}, Food: &Point{X: 8, Y: 8}, Seed: 1, TickMS: 180,
	}
	vacatingTail.tick()
	if vacatingTail.Status != "running" || vacatingTail.Body[0] != (Point{X: 2, Y: 1}) {
		t.Fatalf("vacating tail cell was not legal: %+v", vacatingTail)
	}

	winning := Game{
		Board: Board{Width: 3, Height: 2}, Status: "running",
		Body:      []Point{{X: 1, Y: 0}, {X: 0, Y: 0}, {X: 0, Y: 1}, {X: 1, Y: 1}, {X: 2, Y: 1}},
		Direction: "right", Turns: []string{}, Food: &Point{X: 2, Y: 0}, Seed: 42, Score: 20, TickMS: 168,
	}
	winning.tick()
	if winning.Status != "won" || winning.Food != nil || len(winning.Body) != 6 || winning.Score != 30 {
		t.Fatalf("full board did not win: %+v", winning)
	}
}
