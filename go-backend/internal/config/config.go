package config

import (
	"log"
	"os"
	"github.com/joho/godotenv"
)

type Config struct {
	Port                  string
	PostgresDSN           string
	TimescaleDSN          string
	ValkeyURL             string
	GRPCAddr              string
	JWTSecret             string
	DashboardUsername     string
	DashboardPassword     string // plaintext (dev) — ignored if DashboardPasswordHash is set
	DashboardPasswordHash string // bcrypt hash (production) — takes precedence
	CookieSecure          bool   // send session cookie only over HTTPS
}

// weakSecrets are the known committed defaults. Refusing to start on these
// prevents a deploy from silently signing JWTs with a public secret or
// accepting the public default password (fail-closed).
var weakSecrets = map[string]bool{
	"":                                       true,
	"change-this-secret":                     true,
	"change-this-to-a-random-secret-32chars": true,
	"cryptoswarm2024":                        true,
}

func Load() *Config {
	_ = godotenv.Load("../.env")
	cfg := &Config{
		Port:                  getEnv("GO_PORT", "8080"),
		PostgresDSN:           getEnv("POSTGRES_DSN", "postgresql://postgres:postgres@localhost:5433/cryptoswarm"),
		TimescaleDSN:          getEnv("TIMESCALE_DSN", "postgresql://postgres:postgres@localhost:5434/cryptoswarm_ts"),
		ValkeyURL:             getEnv("VALKEY_URL", "redis://localhost:6379"),
		GRPCAddr:              getEnv("GRPC_ADDR", "localhost:50051"),
		JWTSecret:             os.Getenv("DASHBOARD_SECRET_KEY"),
		DashboardUsername:     getEnv("DASHBOARD_USERNAME", "admin"),
		DashboardPassword:     os.Getenv("DASHBOARD_PASSWORD"),
		DashboardPasswordHash: os.Getenv("DASHBOARD_PASSWORD_HASH"),
		CookieSecure:          getEnv("COOKIE_SECURE", "false") == "true",
	}

	// Fail closed: never fall back to a known/weak secret.
	if weakSecrets[cfg.JWTSecret] {
		log.Fatal("DASHBOARD_SECRET_KEY is unset or a known default — set a strong random value (openssl rand -hex 32)")
	}
	if len(cfg.JWTSecret) < 32 {
		log.Fatal("DASHBOARD_SECRET_KEY is too short — use at least 32 characters")
	}
	// A bcrypt hash (preferred) OR a strong plaintext password must be present.
	if cfg.DashboardPasswordHash == "" && weakSecrets[cfg.DashboardPassword] {
		log.Fatal("Set DASHBOARD_PASSWORD_HASH (bcrypt) or a strong unique DASHBOARD_PASSWORD")
	}

	return cfg
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
