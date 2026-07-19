package api

import (
	"context"
	"log"
	"net/http"
	"strconv"
	"time"
	"github.com/gin-gonic/gin"
	"cryptoswarm/go-backend/internal/db"
)

// internalError logs the real error server-side and returns a generic message
// to the client, so internal DB/driver details are never leaked in responses.
func internalError(c *gin.Context, op string, err error) {
	log.Printf("api error [%s]: %v", op, err)
	c.JSON(http.StatusInternalServerError, gin.H{"error": "internal server error"})
}

func (s *Server) handleStats(c *gin.Context) {
	ctx, cancel := context.WithTimeout(c.Request.Context(), 5*time.Second)
	defer cancel()
	stats, err := db.GetStats(ctx, s.pg)
	if err != nil {
		internalError(c, "stats", err)
		return
	}
	c.JSON(http.StatusOK, stats)
}

func (s *Server) handleTrades(c *gin.Context) {
	limit := queryInt(c, "limit", 50)
	ctx, cancel := context.WithTimeout(c.Request.Context(), 5*time.Second)
	defer cancel()
	trades, err := db.GetTrades(ctx, s.pg, limit)
	if err != nil {
		internalError(c, "trades", err)
		return
	}
	c.JSON(http.StatusOK, orEmpty(trades))
}

func (s *Server) handlePositions(c *gin.Context) {
	if s.grpc == nil {
		c.JSON(http.StatusOK, gin.H{"positions": []any{}, "balance": 0, "equity": 0})
		return
	}
	resp, err := s.grpc.GetLivePositions(c.Request.Context())
	if err != nil {
		c.JSON(http.StatusOK, gin.H{"positions": []any{}, "balance": 0, "equity": 0})
		return
	}
	c.JSON(http.StatusOK, resp)
}

func (s *Server) handleDecisions(c *gin.Context) {
	limit := queryInt(c, "limit", 20)
	ctx, cancel := context.WithTimeout(c.Request.Context(), 5*time.Second)
	defer cancel()
	decisions, err := db.GetDecisions(ctx, s.pg, limit)
	if err != nil {
		internalError(c, "decisions", err)
		return
	}
	c.JSON(http.StatusOK, orEmpty(decisions))
}

func (s *Server) handleMLSignals(c *gin.Context) {
	limit := queryInt(c, "limit", 50)
	ctx, cancel := context.WithTimeout(c.Request.Context(), 5*time.Second)
	defer cancel()
	signals, err := db.GetMLSignals(ctx, s.pg, limit)
	if err != nil {
		internalError(c, "ml-signals", err)
		return
	}
	c.JSON(http.StatusOK, orEmpty(signals))
}

func (s *Server) handlePnlHistory(c *gin.Context) {
	ctx, cancel := context.WithTimeout(c.Request.Context(), 5*time.Second)
	defer cancel()
	points, err := db.GetPnlHistory(ctx, s.pg)
	if err != nil {
		internalError(c, "pnl-history", err)
		return
	}
	c.JSON(http.StatusOK, orEmpty(points))
}

func (s *Server) handleAgents(c *gin.Context) {
	if s.grpc == nil {
		c.JSON(http.StatusOK, gin.H{"agents": []any{}})
		return
	}
	resp, err := s.grpc.GetAgentStatus(c.Request.Context())
	if err != nil {
		c.JSON(http.StatusOK, gin.H{"agents": []any{}})
		return
	}
	c.JSON(http.StatusOK, resp)
}

// orEmpty ensures a nil slice serializes as JSON [] instead of null,
// which the frontend cannot render.
func orEmpty[T any](s []T) []T {
	if s == nil {
		return []T{}
	}
	return s
}

func queryInt(c *gin.Context, key string, def int) int {
	v, err := strconv.Atoi(c.Query(key))
	if err != nil || v <= 0 {
		return def
	}
	return v
}
