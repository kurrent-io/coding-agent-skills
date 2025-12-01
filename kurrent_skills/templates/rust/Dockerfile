FROM rust:latest AS build

WORKDIR /app

# Create dummy project to cache dependencies
RUN cargo new --bin kurrentdb-example
WORKDIR /app/kurrentdb-example

COPY Cargo.toml ./
RUN mkdir -p src && echo "fn main() {}" > src/main.rs
RUN cargo build --release || true

# Copy actual source and build
COPY src ./src
RUN touch src/main.rs && cargo build --release --bin example

FROM debian:trixie-slim
WORKDIR /app

RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*

COPY --from=build /app/kurrentdb-example/target/release/example .

# Use environment variable for connection string
ENV KURRENTDB_CONNECTION_STRING=kurrentdb://localhost:2113?tls=false

CMD ["./example"]
