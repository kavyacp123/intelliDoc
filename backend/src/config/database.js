const { Sequelize } = require('sequelize');

// ─── Sequelize Instance ────────────────────────────────────────────────────────
// Connects via DATABASE_URL (Supabase / any PostgreSQL provider).
// Falls back to individual DB_* vars for local dev.
// ────────────────────────────────────────────────────────────────────────────────

const connectionString = process.env.DATABASE_URL;

const sequelize = connectionString
    ? new Sequelize(connectionString, {
        dialect: 'postgres',
        logging: process.env.NODE_ENV === 'development' ? console.log : false,
        dialectOptions: process.env.DB_SSL === 'true' ? {
            ssl: { require: true, rejectUnauthorized: false },
        } : {},
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

async function connectDB() {
    try {
        await sequelize.authenticate();
        console.log('✅  PostgreSQL connected.');
        const syncOpts = process.env.NODE_ENV === 'development' ? { alter: true } : {};
        await sequelize.sync(syncOpts);
        console.log('✅  Models synchronised.');
    } catch (error) {
        console.error('❌  PostgreSQL connection failed:', error.message);
        process.exit(1);
    }
}

module.exports = { sequelize, connectDB };
