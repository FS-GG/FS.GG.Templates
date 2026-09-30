package main

import "fmt"

const (
	boardWidth     = 32
	boardHeight    = 18
	initialSeed    = uint32(633)
	initialTickMS  = 180
	minimumTickMS  = 60
	turnQueueLimit = 2
)

type Point struct {
	X int `json:"x"`
	Y int `json:"y"`
}

type Board struct {
	Width  int `json:"width"`
	Height int `json:"height"`
}

type Game struct {
	Board            Board    `json:"board"`
	Status           string   `json:"status"`
	Body             []Point  `json:"body"`
	Direction        string   `json:"direction"`
	Turns            []string `json:"turns"`
	Food             *Point   `json:"food"`
	Seed             uint32   `json:"seed"`
	Score            int      `json:"score"`
	TickMS           int      `json:"tickMs"`
	ClockRemainderMS int      `json:"clockRemainderMs"`
}

var directionVectors = map[string]Point{
	"up": {X: 0, Y: -1}, "down": {X: 0, Y: 1},
	"left": {X: -1, Y: 0}, "right": {X: 1, Y: 0},
}

func newGameForBoard(seed uint32, board Board, body []Point) Game {
	body = append([]Point(nil), body...)
	food, nextSeed := placeFood(body, seed, board)
	return Game{Board: board, Status: "ready", Body: body, Direction: "right", Turns: []string{}, Food: food, Seed: nextSeed, TickMS: initialTickMS}
}

func newGame() Game {
	return newGameForBoard(initialSeed, Board{Width: boardWidth, Height: boardHeight}, []Point{{X: 16, Y: 9}, {X: 15, Y: 9}, {X: 14, Y: 9}})
}

func nextRandom(seed uint32) uint32 {
	seed ^= seed << 13
	seed ^= seed >> 17
	seed ^= seed << 5
	return seed
}

func placeFood(body []Point, seed uint32, board Board) (*Point, uint32) {
	occupied := make(map[Point]bool, len(body))
	for _, point := range body {
		occupied[point] = true
	}
	free := make([]Point, 0, board.Width*board.Height-len(body))
	for y := 0; y < board.Height; y++ {
		for x := 0; x < board.Width; x++ {
			point := Point{X: x, Y: y}
			if !occupied[point] {
				free = append(free, point)
			}
		}
	}
	next := nextRandom(seed)
	if len(free) == 0 {
		return nil, next
	}
	food := free[int(next%uint32(len(free)))]
	return &food, next
}

func tickInterval(score int) int {
	interval := initialTickMS - (score/10)*6
	if interval < minimumTickMS {
		return minimumTickMS
	}
	return interval
}

func opposite(first, second string) bool {
	a, aOK := directionVectors[first]
	b, bOK := directionVectors[second]
	return aOK && bOK && a.X+b.X == 0 && a.Y+b.Y == 0
}

func (game *Game) turn(direction string) (bool, string) {
	if game.Status != "running" {
		return false, "game-not-running"
	}
	if _, ok := directionVectors[direction]; !ok {
		return false, "direction-invalid"
	}
	if len(game.Turns) >= turnQueueLimit {
		return false, "turn-queue-full"
	}
	previous := game.Direction
	if len(game.Turns) > 0 {
		previous = game.Turns[len(game.Turns)-1]
	}
	if previous == direction {
		return false, "turn-duplicate"
	}
	if opposite(previous, direction) {
		return false, "turn-reversal-refused"
	}
	game.Turns = append(game.Turns, direction)
	return true, ""
}

func (game *Game) tick() {
	if game.Status != "running" {
		return
	}
	direction := game.Direction
	if len(game.Turns) > 0 {
		candidate := game.Turns[0]
		game.Turns = game.Turns[1:]
		if !opposite(game.Direction, candidate) {
			direction = candidate
		}
	}
	vector := directionVectors[direction]
	head := Point{X: game.Body[0].X + vector.X, Y: game.Body[0].Y + vector.Y}
	out := head.X < 0 || head.Y < 0 || head.X >= game.Board.Width || head.Y >= game.Board.Height
	growing := game.Food != nil && head == *game.Food
	collisionLength := len(game.Body)
	if !growing {
		collisionLength--
	}
	collides := false
	for _, point := range game.Body[:collisionLength] {
		if point == head {
			collides = true
			break
		}
	}
	game.Direction = direction
	if out || collides {
		game.Status = "lost"
		game.Turns = []string{}
		return
	}
	game.Body = append([]Point{head}, game.Body...)
	if !growing {
		game.Body = game.Body[:len(game.Body)-1]
		return
	}
	game.Score += 10
	game.TickMS = tickInterval(game.Score)
	game.Food, game.Seed = placeFood(game.Body, game.Seed, game.Board)
	if game.Food == nil {
		game.Status = "won"
		game.Turns = []string{}
	}
}

func (game *Game) advance(milliseconds int) (bool, string) {
	if game.Status != "running" {
		return false, "game-not-running"
	}
	if milliseconds <= 0 || milliseconds > 60_000 {
		return false, "advance-milliseconds-invalid"
	}
	game.ClockRemainderMS += milliseconds
	for game.Status == "running" && game.ClockRemainderMS >= game.TickMS {
		game.ClockRemainderMS -= game.TickMS
		game.tick()
	}
	return true, ""
}

func (game *Game) apply(command Command) (bool, string) {
	switch command.Type {
	case "state":
		return true, ""
	case "start":
		if game.Status != "ready" {
			return false, "start-refused"
		}
		game.Status = "running"
		return true, ""
	case "direction":
		return game.turn(command.Direction)
	case "advance":
		return game.advance(command.Milliseconds)
	case "pause":
		if game.Status != "running" {
			return false, "pause-refused"
		}
		game.Status = "paused"
		game.ClockRemainderMS = 0
		return true, ""
	case "resume":
		if game.Status != "paused" {
			return false, "resume-refused"
		}
		game.Status = "running"
		return true, ""
	case "restart":
		*game = newGameForBoard(initialSeed, game.Board, []Point{{X: 16, Y: 9}, {X: 15, Y: 9}, {X: 14, Y: 9}})
		return true, ""
	default:
		return false, fmt.Sprintf("command-unsupported:%s", command.Type)
	}
}
