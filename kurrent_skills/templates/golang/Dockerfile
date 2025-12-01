FROM golang:1.23-alpine AS build

WORKDIR /app

# Install git for go mod download
RUN apk add --no-cache git

COPY go.mod ./
COPY main.go projection.go ./
RUN go mod tidy && go build -o main .

FROM alpine:latest
WORKDIR /app

# Install CA certificates for TLS and DNS resolution
RUN apk add --no-cache ca-certificates

COPY --from=build /app/main .

# Use environment variable for connection string
ENV KURRENTDB_CONNECTION_STRING=esdb://localhost:2113?tls=false

CMD ["./main"]
