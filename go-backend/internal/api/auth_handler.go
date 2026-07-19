package api

import (
	"crypto/subtle"
	"net/http"
	"github.com/gin-gonic/gin"
	"golang.org/x/crypto/bcrypt"
	"cryptoswarm/go-backend/internal/auth"
)

type loginRequest struct {
	Username string `json:"username" binding:"required"`
	Password string `json:"password" binding:"required"`
}

// verifyPassword checks a submitted password against the configured credential.
// Prefers a bcrypt hash when one is set; otherwise falls back to a
// constant-time comparison against the plaintext password (dev only).
func (s *Server) verifyPassword(submitted string) bool {
	if s.cfg.DashboardPasswordHash != "" {
		return bcrypt.CompareHashAndPassword(
			[]byte(s.cfg.DashboardPasswordHash), []byte(submitted),
		) == nil
	}
	return subtle.ConstantTimeCompare([]byte(submitted), []byte(s.cfg.DashboardPassword)) == 1
}

func (s *Server) handleLogin(c *gin.Context) {
	var req loginRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "username and password required"})
		return
	}
	userOK := subtle.ConstantTimeCompare([]byte(req.Username), []byte(s.cfg.DashboardUsername)) == 1
	if !userOK || !s.verifyPassword(req.Password) {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "invalid credentials"})
		return
	}
	token, err := auth.IssueToken(req.Username, s.cfg.JWTSecret)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "could not issue token"})
		return
	}
	auth.SetCookie(c.Writer, token, s.cfg.CookieSecure)
	c.JSON(http.StatusOK, gin.H{"username": req.Username})
}

func (s *Server) handleLogout(c *gin.Context) {
	auth.ClearCookie(c.Writer)
	c.JSON(http.StatusOK, gin.H{"ok": true})
}
