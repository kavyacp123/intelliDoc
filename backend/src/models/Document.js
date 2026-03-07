const { DataTypes } = require('sequelize');
const { sequelize } = require('../config/database');

// ─── Document Model ────────────────────────────────────────────────────────────
// Tracks uploaded files and their processing lifecycle.
// Status flow: uploaded → processing → completed | failed | needs_review
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
        },
        original_name: {
            type: DataTypes.STRING,
            allowNull: false,
        },
        mime_type: {
            type: DataTypes.STRING,
            allowNull: false,
        },
        file_size: {
            type: DataTypes.INTEGER,
            allowNull: false,
        },
        page_count: {
            type: DataTypes.INTEGER,
            allowNull: true,
        },
        status: {
            type: DataTypes.ENUM('uploaded', 'processing', 'completed', 'failed', 'needs_review'),
            defaultValue: 'uploaded',
            allowNull: false,
        },
        error_message: {
            type: DataTypes.TEXT,
            allowNull: true,
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
