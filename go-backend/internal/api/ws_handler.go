package api

import "github.com/gin-gonic/gin"

func (s *Server) handleWS(c *gin.Context) {
	s.hub.ServeWS(c.Writer, c.Request)
}
