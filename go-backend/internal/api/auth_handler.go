package api

import (
	"net/http"
	"github.com/gin-gonic/gin"
	"cryptoswarm/go-backend/internal/auth"
)

type loginRequest struct {
	Username string `json:"username" binding:"required"`
	Password string `json:"password" binding:"required"`
}

func (s *Server) handleLogin(c *gin.Context) {
	var req loginRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "username and password required"})
		return
	}
	if req.Username != s.cfg.DashboardUsername || req.Password != s.cfg.DashboardPassword {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "invalid credentials"})
		return
	}
	token, err := auth.IssueToken(req.Username, s.cfg.JWTSecret)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "could not issue token"})
		return
	}
	auth.SetCookie(c.Writer, token)
	c.JSON(http.StatusOK, gin.H{"username": req.Username})
}

func (s *Server) handleLogout(c *gin.Context) {
	auth.ClearCookie(c.Writer)
	c.JSON(http.StatusOK, gin.H{"ok": true})
}
