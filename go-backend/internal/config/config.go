package config

import (
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

func Load() *Config {
	_ = godotenv.Load("../.env")
	return &Config{
		Port:              getEnv("GO_PORT", "8080"),
		PostgresDSN:       getEnv("POSTGRES_DSN", "postgresql://postgres:postgres@localhost:5433/cryptoswarm"),
		TimescaleDSN:      getEnv("TIMESCALE_DSN", "postgresql://postgres:postgres@localhost:5434/cryptoswarm_ts"),
		ValkeyURL:         getEnv("VALKEY_URL", "redis://localhost:6379"),
		GRPCAddr:          getEnv("GRPC_ADDR", "localhost:50051"),
		JWTSecret:         getEnv("DASHBOARD_SECRET_KEY", "change-this-secret"),
		DashboardUsername: getEnv("DASHBOARD_USERNAME", "admin"),
		DashboardPassword: getEnv("DASHBOARD_PASSWORD", "cryptoswarm2024"),
	}
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
