const { DataTypes } = require('sequelize');
const { sequelize } = require('../config/database');

// ─── Document Model ────────────────────────────────────────────────────────────
// Represents an uploaded financial document (PDF invoice / bill).
// Status tracks the processing pipeline: uploaded → processing → completed|failed
// ────────────────────────────────────────────────────────────────────────────────

const Document = sequelize.define(
    'Document',
    {
        id: {
            type: DataTypes.UUID,
            defaultValue: DataTypes.UUIDV4,
            primaryKey: true,
        },
        filename: {
            type: DataTypes.STRING,
            allowNull: false,
            validate: { notEmpty: true },
        },
        original_name: {
            type: DataTypes.STRING,
            allowNull: false,
            comment: 'Original filename as uploaded by the user',
        },
        mime_type: {
            type: DataTypes.STRING,
            allowNull: false,
        },
        file_size: {
            type: DataTypes.INTEGER,
            allowNull: false,
            comment: 'File size in bytes',
        },
        status: {
            type: DataTypes.ENUM('uploaded', 'processing', 'completed', 'failed'),
            defaultValue: 'uploaded',
            allowNull: false,
        },
        error_message: {
            type: DataTypes.TEXT,
            allowNull: true,
            comment: 'Stores the error details when status is failed',
        },
        uploaded_at: {
            type: DataTypes.DATE,
            defaultValue: DataTypes.NOW,
        },
    },
    {
        tableName: 'documents',
        timestamps: false,
    }
);

module.exports = Document;
