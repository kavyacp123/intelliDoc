const { DataTypes } = require('sequelize');
const { sequelize } = require('../config/database');
const Document = require('./Document');

// ─── Invoice Record Model ──────────────────────────────────────────────────────
// Stores structured financial data extracted by the Python worker.
// One document can produce multiple records (one per page or per invoice found).
// ────────────────────────────────────────────────────────────────────────────────

const InvoiceRecord = sequelize.define(
    'InvoiceRecord',
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
        page_number: {
            type: DataTypes.INTEGER,
            allowNull: true,
        },
        vendor: {
            type: DataTypes.STRING,
            allowNull: true,
        },
        invoice_number: {
            type: DataTypes.STRING,
            allowNull: true,
        },
        invoice_date: {
            type: DataTypes.DATEONLY,
            allowNull: true,
        },
        subtotal: {
            type: DataTypes.DECIMAL(14, 2),
            allowNull: true,
        },
        cgst: {
            type: DataTypes.DECIMAL(14, 2),
            allowNull: true,
        },
        sgst: {
            type: DataTypes.DECIMAL(14, 2),
            allowNull: true,
        },
        igst: {
            type: DataTypes.DECIMAL(14, 2),
            allowNull: true,
        },
        grand_total: {
            type: DataTypes.DECIMAL(14, 2),
            allowNull: true,
        },
        confidence_score: {
            type: DataTypes.FLOAT,
            allowNull: true,
        },
        raw_ocr_text: {
            type: DataTypes.TEXT,
            allowNull: true,
        },
        line_items: {
            type: DataTypes.JSONB,
            allowNull: true,
            comment: 'Table rows extracted by Camelot: [{description, qty, rate, amount}]',
        },
        created_at: {
            type: DataTypes.DATE,
            defaultValue: DataTypes.NOW,
        },
    },
    {
        tableName: 'invoice_records',
        timestamps: false,
    }
);

// ─── Associations ──────────────────────────────────────────────────────────────
Document.hasMany(InvoiceRecord, { foreignKey: 'document_id', as: 'invoiceRecords' });
InvoiceRecord.belongsTo(Document, { foreignKey: 'document_id', as: 'document' });

module.exports = InvoiceRecord;
