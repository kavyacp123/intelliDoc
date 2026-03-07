const { Sequelize } = require('sequelize');

// ─── Sequelize Instance ────────────────────────────────────────────────────────
// Connects via DATABASE_URL (Supabase / any PostgreSQL provider).
// Falls back to individual DB_* env vars for local development.
// ────────────────────────────────────────────────────────────────────────────────

const connectionString = process.env.DATABASE_URL;

const sequelize = connectionString
  ? new Sequelize(connectionString, {
    dialect: 'postgres',
    logging: process.env.NODE_ENV === 'development' ? console.log : false,
    dialectOptions: {
      ssl: {
        require: true,
        rejectUnauthorized: false, // Supabase uses self-signed certs
      },
    },
    pool: { max: 10, min: 2, acquire: 30000, idle: 10000 },
  })
  : new Sequelize(
    process.env.DB_NAME,
    process.env.DB_USER,
    process.env.DB_PASSWORD,
    {
      host: process.env.DB_HOST || 'localhost',
      port: process.env.DB_PORT || 5432,
      dialect: 'postgres',
      logging: process.env.NODE_ENV === 'development' ? console.log : false,
      pool: { max: 10, min: 2, acquire: 30000, idle: 10000 },
    }
  );

/**
 * connectDB – authenticates the database connection and syncs all
 * registered models. Uses `alter: true` in development so schema
 * changes are applied automatically without dropping tables.
 */
async function connectDB() {
  try {
    await sequelize.authenticate();
    console.log('✅  PostgreSQL connected successfully.');

    // Sync models – alter in dev to apply column changes automatically
    const syncOptions =
      process.env.NODE_ENV === 'development' ? { alter: true } : {};
    await sequelize.sync(syncOptions);
    console.log('✅  Database models synchronised.');
  } catch (error) {
    console.error('❌  Unable to connect to PostgreSQL:', error.message);
    process.exit(1);
  }
}

module.exports = { sequelize, connectDB };
