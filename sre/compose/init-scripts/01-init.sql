-- Инициализационный скрипт для PostgreSQL
-- Этот скрипт выполняется при первом запуске контейнера

-- Создание расширений (если нужны)
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
-- CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Настройка кодировки и локали
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;

-- Комментарий о базе данных
COMMENT ON DATABASE cyberpolygon IS 'Cyberpolygon project database';

-- Логирование для отладки
DO $$
BEGIN
    RAISE NOTICE 'Database initialization completed successfully';
END $$;
