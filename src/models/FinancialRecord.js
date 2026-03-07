const { DataTypes } = require('sequelize');
const { sequelize } = require('../config/database');
const Document = require('./Document');

// ─── Financial Record Model ────────────────────────────────────────────────────
// Stores the structured financial data extracted from a processed document.
// Each document produces exactly one financial record on successful extraction.
// ────────────────────────────────────────────────────────────────────────────────

const FinancialRecord = sequelize.define(
    'FinancialRecord',
    {
        id: {
            type: DataTypes.UUID,
            defaultValue: DataTypes.UUIDV4,
            primaryKey: true,
        },
        document_id: {
            type: DataTypes.UUID,
            allowNull: false,
            references: { model: 'documents', key: 'id' },
        },
        invoice_date: {
            type: DataTypes.DATEONLY,
            allowNull: true,
            comment: 'Date found on the invoice, may be null if not detected',
        },
        vendor: {
            type: DataTypes.STRING,
            allowNull: true,
            comment: 'Vendor / payee name extracted from document',
        },
        total_amount: {
            type: DataTypes.DECIMAL(12, 2),
            allowNull: true,
            comment: 'Total invoice amount in base currency',
        },
        gst: {
            type: DataTypes.DECIMAL(12, 2),
            allowNull: true,
            comment: 'GST / tax amount',
        },
        raw_text: {
            type: DataTypes.TEXT,
            allowNull: true,
            comment: 'Full extracted text for debugging / re-processing',
        },
        extraction_method: {
            type: DataTypes.ENUM('pdf-parse', 'ocr'),
            allowNull: true,
        },
        created_at: {
            type: DataTypes.DATE,
            defaultValue: DataTypes.NOW,
        },
    },
    {
        tableName: 'financial_records',
        timestamps: false,
    }
);

// ─── Associations ──────────────────────────────────────────────────────────────
Document.hasMany(FinancialRecord, {
    foreignKey: 'document_id',
    as: 'financialRecords',
});
FinancialRecord.belongsTo(Document, {
    foreignKey: 'document_id',
    as: 'document',
});

module.exports = FinancialRecord;
