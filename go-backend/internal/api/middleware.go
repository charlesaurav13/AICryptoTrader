package api

import (
	"net/http"
	"github.com/gin-gonic/gin"
	"cryptoswarm/go-backend/internal/auth"
)

func (s *Server) requireAuth() gin.HandlerFunc {
	return func(c *gin.Context) {
		token := auth.GetToken(c.Request)
		if token == "" {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "not authenticated"})
			return
		}
		claims, err := auth.ValidateToken(token, s.cfg.JWTSecret)
		if err != nil {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "session expired"})
			return
		}
		c.Set("username", claims.Username)
		c.Next()
	}
}
