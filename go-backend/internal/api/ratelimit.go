package api

import (
	"net/http"
	"sync"
	"time"
	"github.com/gin-gonic/gin"
)

// loginLimiter is a small in-memory fixed-window rate limiter keyed by client
// IP. It exists to slow credential brute-forcing against /auth/login. It is
// per-process (not shared across replicas) — good enough for a single-node
// deployment; use a shared store (Valkey) if this ever scales horizontally.
type loginLimiter struct {
	mu       sync.Mutex
	hits     map[string]*window
	max      int
	interval time.Duration
}

type window struct {
	count int
	reset time.Time
}

func newLoginLimiter(max int, interval time.Duration) *loginLimiter {
	l := &loginLimiter{
		hits:     make(map[string]*window),
		max:      max,
		interval: interval,
	}
	go l.gc()
	return l
}

// allow reports whether the given key may make another attempt now.
func (l *loginLimiter) allow(key string) bool {
	l.mu.Lock()
	defer l.mu.Unlock()
	now := time.Now()
	w, ok := l.hits[key]
	if !ok || now.After(w.reset) {
		l.hits[key] = &window{count: 1, reset: now.Add(l.interval)}
		return true
	}
	if w.count >= l.max {
		return false
	}
	w.count++
	return true
}

// gc periodically drops expired windows so the map does not grow unbounded.
func (l *loginLimiter) gc() {
	ticker := time.NewTicker(10 * time.Minute)
	defer ticker.Stop()
	for range ticker.C {
		l.mu.Lock()
		now := time.Now()
		for k, w := range l.hits {
			if now.After(w.reset) {
				delete(l.hits, k)
			}
		}
		l.mu.Unlock()
	}
}

func (l *loginLimiter) middleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		if !l.allow(c.ClientIP()) {
			c.AbortWithStatusJSON(http.StatusTooManyRequests, gin.H{
				"error": "too many login attempts — try again later",
			})
			return
		}
		c.Next()
	}
}
