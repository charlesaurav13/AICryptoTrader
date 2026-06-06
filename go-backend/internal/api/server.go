package api

import (
	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5/pgxpool"
	"cryptoswarm/go-backend/internal/config"
	"cryptoswarm/go-backend/internal/grpcclient"
	"cryptoswarm/go-backend/internal/ws"
)

type Server struct {
	cfg    *config.Config
	pg     *pgxpool.Pool
	ts     *pgxpool.Pool
	grpc   *grpcclient.Client
	hub    *ws.Hub
	engine *gin.Engine
}

func NewServer(cfg *config.Config, pg, ts *pgxpool.Pool, grpc *grpcclient.Client, hub *ws.Hub) *Server {
	s := &Server{cfg: cfg, pg: pg, ts: ts, grpc: grpc, hub: hub}
	s.engine = gin.Default()
	s.engine.Use(corsMiddleware())
	s.routes()
	return s
}

func (s *Server) Run(addr string) error {
	return s.engine.Run(addr)
}

func (s *Server) routes() {
	s.engine.POST("/auth/login", s.handleLogin)
	s.engine.POST("/auth/logout", s.handleLogout)
	s.engine.GET("/health", func(c *gin.Context) { c.JSON(200, gin.H{"status": "ok"}) })

	api := s.engine.Group("/api", s.requireAuth())
	api.GET("/stats", s.handleStats)
	api.GET("/trades", s.handleTrades)
	api.GET("/positions", s.handlePositions)
	api.GET("/decisions", s.handleDecisions)
	api.GET("/ml-signals", s.handleMLSignals)
	api.GET("/pnl-history", s.handlePnlHistory)
	api.GET("/agents", s.handleAgents)

	s.engine.GET("/ws", s.requireAuth(), s.handleWS)
}

// allowedOrigins covers local dev on any port + the Docker service name.
var allowedOrigins = map[string]bool{
	"http://localhost:3000": true,
	"http://localhost:3001": true,
	"http://localhost:3002": true,
	"http://cs-web:3000":   true,
}

func corsMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		origin := c.Request.Header.Get("Origin")
		if allowedOrigins[origin] {
			c.Header("Access-Control-Allow-Origin", origin)
		}
		c.Header("Access-Control-Allow-Credentials", "true")
		c.Header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
		c.Header("Access-Control-Allow-Headers", "Content-Type")
		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(204)
			return
		}
		c.Next()
	}
}
