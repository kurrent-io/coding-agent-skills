FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src

COPY *.fsproj ./
RUN dotnet restore

COPY *.fs ./
RUN dotnet publish -c Release -o /app

FROM mcr.microsoft.com/dotnet/runtime:8.0
WORKDIR /app
COPY --from=build /app .

# Use environment variable for connection string
ENV KURRENTDB_CONNECTION_STRING=kurrentdb://localhost:2113?tls=false

ENTRYPOINT ["dotnet", "KurrentDbExample.dll"]
