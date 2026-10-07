-- Vector search for the copilot database (POSTGRES_DB)
CREATE EXTENSION IF NOT EXISTS vector;

-- Separate database for the mock customer system
CREATE DATABASE lumora_commerce;
