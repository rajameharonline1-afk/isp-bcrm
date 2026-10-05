-- ফাইল: backend/scripts/init_db.sql
-- এই ফাইলটি PostgreSQL database initialization script। FreeRADIUS-এর জন্য আলাদা database তৈরি করে।

-- FreeRADIUS-এর জন্য আলাদা database তৈরি করা
CREATE DATABASE radius;

-- FreeRADIUS user তৈরি করা (নিজের password দিন)
-- CREATE USER radius_user WITH PASSWORD 'radius_password';
-- GRANT ALL PRIVILEGES ON DATABASE radius TO radius_user;
