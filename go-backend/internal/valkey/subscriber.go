package valkey

import (
	"context"
	"encoding/json"
	"log"
	"github.com/redis/go-redis/v9"
	"cryptoswarm/go-backend/internal/ws"
)

type Subscriber struct {
	client *redis.Client
	hub    *ws.Hub
}

func NewSubscriber(url string, hub *ws.Hub) *Subscriber {
	opt, err := redis.ParseURL(url)
	if err != nil {
		log.Printf("valkey: bad URL %s: %v", url, err)
		opt = &redis.Options{Addr: "localhost:6379"}
	}
	return &Subscriber{client: redis.NewClient(opt), hub: hub}
}

func (s *Subscriber) Run() {
	ctx := context.Background()
	ps := s.client.PSubscribe(ctx, "signal.execute", "position.update", "circuit.tripped", "agent.result.*")
	ch := ps.Channel()
	log.Println("Valkey subscriber running")
	for msg := range ch {
		var payload any
		if err := json.Unmarshal([]byte(msg.Payload), &payload); err != nil {
			payload = msg.Payload
		}
		s.hub.Broadcast(msg.Channel, payload)
	}
}
