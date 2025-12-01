FROM node:20-slim

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY *.js ./

# Use environment variable for connection string
ENV KURRENTDB_CONNECTION_STRING=kurrentdb://localhost:2113?tls=false

CMD ["node", "example.js"]
