FROM golang:1.23-alpine AS build

WORKDIR /app

COPY go.mod ./
COPY main.go ./
RUN go mod tidy && go build -o main .

FROM alpine:latest
WORKDIR /app
COPY --from=build /app/main .

# Use environment variable for connection string
ENV KURRENTDB_CONNECTION_STRING=kurrentdb://localhost:2113?tls=false

CMD ["./main"]
