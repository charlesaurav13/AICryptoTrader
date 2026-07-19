package config

import (
	"log"
	"os"
	"github.com/joho/godotenv"
)

type Config struct {
	Port              string
	PostgresDSN       string
	TimescaleDSN      string
	ValkeyURL         string
	GRPCAddr          string
	JWTSecret         string
	DashboardUsername string
	DashboardPassword string
}

// weakSecrets are the known committed defaults. Refusing to start on these
// prevents a deploy from silently signing JWTs with a public secret or
// accepting the public default password (fail-closed).
var weakSecrets = map[string]bool{
	"":                                        true,
	"change-this-secret":                      true,
	"change-this-to-a-random-secret-32chars":  true,
	"cryptoswarm2024":                         true,
}

func Load() *Config {
	_ = godotenv.Load("../.env")
	cfg := &Config{
		Port:              getEnv("GO_PORT", "8080"),
		PostgresDSN:       getEnv("POSTGRES_DSN", "postgresql://postgres:postgres@localhost:5433/cryptoswarm"),
		TimescaleDSN:      getEnv("TIMESCALE_DSN", "postgresql://postgres:postgres@localhost:5434/cryptoswarm_ts"),
		ValkeyURL:         getEnv("VALKEY_URL", "redis://localhost:6379"),
		GRPCAddr:          getEnv("GRPC_ADDR", "localhost:50051"),
		JWTSecret:         os.Getenv("DASHBOARD_SECRET_KEY"),
		DashboardUsername: getEnv("DASHBOARD_USERNAME", "admin"),
		DashboardPassword: os.Getenv("DASHBOARD_PASSWORD"),
	}

	// Fail closed: never fall back to a known/weak secret or password.
	if weakSecrets[cfg.JWTSecret] {
		log.Fatal("DASHBOARD_SECRET_KEY is unset or a known default — set a strong random value (openssl rand -hex 32)")
	}
	if len(cfg.JWTSecret) < 32 {
		log.Fatal("DASHBOARD_SECRET_KEY is too short — use at least 32 characters")
	}
	if weakSecrets[cfg.DashboardPassword] {
		log.Fatal("DASHBOARD_PASSWORD is unset or the known default — set a strong unique password")
	}

	return cfg
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
