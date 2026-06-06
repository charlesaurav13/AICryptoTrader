package main

import (
	"log"
	"cryptoswarm/go-backend/internal/api"
	"cryptoswarm/go-backend/internal/config"
	"cryptoswarm/go-backend/internal/db"
	"cryptoswarm/go-backend/internal/grpcclient"
	"cryptoswarm/go-backend/internal/valkey"
	"cryptoswarm/go-backend/internal/ws"
)

func main() {
	cfg := config.Load()

	pgPool, err := db.NewPostgres(cfg.PostgresDSN)
	if err != nil {
		log.Fatalf("postgres: %v", err)
	}
	defer pgPool.Close()

	tsPool, err := db.NewTimescale(cfg.TimescaleDSN)
	if err != nil {
		log.Fatalf("timescale: %v", err)
	}
	defer tsPool.Close()

	grpcClient, err := grpcclient.New(cfg.GRPCAddr)
	if err != nil {
		log.Printf("grpc: %v (positions will be empty)", err)
	}

	hub := ws.NewHub()
	go hub.Run()

	vk := valkey.NewSubscriber(cfg.ValkeyURL, hub)
	go vk.Run()

	srv := api.NewServer(cfg, pgPool, tsPool, grpcClient, hub)
	log.Printf("Go backend listening on :%s", cfg.Port)
	if err := srv.Run(":" + cfg.Port); err != nil {
		log.Fatalf("server: %v", err)
	}
}
