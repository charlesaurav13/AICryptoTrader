package main

import (
	"flag"
	"io"
	"log"
	"net/http"
	"os"
	"cryptoswarm/go-backend/internal/api"
	"cryptoswarm/go-backend/internal/config"
	"cryptoswarm/go-backend/internal/db"
	"cryptoswarm/go-backend/internal/grpcclient"
	"cryptoswarm/go-backend/internal/valkey"
	"cryptoswarm/go-backend/internal/ws"
)

func main() {
	hc := flag.Bool("healthcheck", false, "ping /health and exit 0/1")
	flag.Parse()

	// ── Healthcheck mode — used by HEALTHCHECK in the Dockerfile ──────────────
	// Runs a quick HTTP GET to localhost:8080/health and exits.
	// This lets distroless containers (no shell/curl) still health-check cleanly.
	if *hc {
		resp, err := http.Get("http://localhost:8080/health")
		if err != nil {
			log.Printf("healthcheck: %v", err)
			os.Exit(1)
		}
		_, _ = io.Copy(io.Discard, resp.Body)
		resp.Body.Close()
		if resp.StatusCode != http.StatusOK {
			log.Printf("healthcheck: status %d", resp.StatusCode)
			os.Exit(1)
		}
		os.Exit(0)
	}

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
