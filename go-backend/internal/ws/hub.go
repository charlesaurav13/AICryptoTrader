package ws

import (
	"encoding/json"
	"log"
	"net/http"
	"sync"
	"github.com/gorilla/websocket"
)

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool { return true },
}

type Event struct {
	Topic   string `json:"topic"`
	Payload any    `json:"payload"`
}

type Hub struct {
	clients map[*websocket.Conn]struct{}
	mu      sync.RWMutex
	send    chan Event
}

func NewHub() *Hub {
	return &Hub{clients: make(map[*websocket.Conn]struct{}), send: make(chan Event, 256)}
}

func (h *Hub) Run() {
	for event := range h.send {
		data, err := json.Marshal(event)
		if err != nil {
			continue
		}
		h.mu.RLock()
		for conn := range h.clients {
			if err := conn.WriteMessage(websocket.TextMessage, data); err != nil {
				conn.Close()
			}
		}
		h.mu.RUnlock()
	}
}

func (h *Hub) Broadcast(topic string, payload any) {
	select {
	case h.send <- Event{Topic: topic, Payload: payload}:
	default:
		log.Println("ws hub: send buffer full, dropping event")
	}
}

func (h *Hub) ServeWS(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		return
	}
	h.mu.Lock()
	h.clients[conn] = struct{}{}
	h.mu.Unlock()
	defer func() {
		h.mu.Lock()
		delete(h.clients, conn)
		h.mu.Unlock()
		conn.Close()
	}()
	for {
		if _, _, err := conn.ReadMessage(); err != nil {
			break
		}
	}
}
