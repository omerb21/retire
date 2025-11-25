/**
 * AssetItem Component
 * ===================
 * Component for displaying a single capital asset item
 */

import React from 'react';
import { CapitalAsset, ASSET_TYPES } from '../../../types/capitalAsset';
import { formatDateToDDMMYY } from '../../../utils/dateUtils';
import { formatCurrency } from '../../../lib/validation';
import './AssetItem.css';

const formatMoney = (value: number | null | undefined): string => {
  const numeric = value ?? 0;
  const formatted = formatCurrency(numeric);
  return formatted.replace('₪', '').trim();
};

interface AssetItemProps {
  asset: CapitalAsset;
  onEdit: (asset: CapitalAsset) => void;
  onDelete: (assetId: number) => void;
}

export function AssetItem({ asset, onEdit, onDelete }: AssetItemProps) {
  return (
    <div className="asset-item-container">
      <div className="asset-item-grid">
        <div className="asset-item-header">
          {asset.asset_name || asset.description || "נכס ללא שם"}
        </div>
        
        <div className="asset-item-columns">
          <div className="asset-item-card">
            <div className="asset-item-card-title">פרטי נכס</div>
            <div><strong>סוג נכס:</strong> {ASSET_TYPES.find(t => t.value === asset.asset_type)?.label || asset.asset_type}</div>
            <div><strong>תשלום:</strong> ₪{formatMoney(asset.monthly_income || 0)}</div>
            <div><strong>ערך נוכחי:</strong> ₪{formatMoney(asset.current_value || 0)}</div>
            <div><strong>תשואה שנתית:</strong> {
              asset.annual_return_rate > 1 ? asset.annual_return_rate : 
              asset.annual_return_rate ? (asset.annual_return_rate * 100) : 
              asset.annual_return || 0
            }%</div>
          </div>
          
          <div className="asset-item-card">
            <div className="asset-item-card-title">תאריך ומס</div>
            <div><strong>תאריך תשלום:</strong> {asset.start_date ? formatDateToDDMMYY(new Date(asset.start_date)) : "לא צוין"}</div>
            <div><strong>הצמדה:</strong> {
              asset.indexation_method === "none" ? "ללא" :
              asset.indexation_method === "fixed" ? `קבועה ${asset.fixed_rate}%` :
              "למדד"
            }</div>
          </div>
        </div>
        
        <div className="asset-item-tax-card">
          <div className="asset-item-tax-title">מיסוי</div>
          <div><strong>יחס מס:</strong> {
            asset.tax_treatment === "exempt" ? "פטור ממס" :
            asset.tax_treatment === "taxable" ? "חייב במס רגיל" :
            asset.tax_treatment === "capital_gains" ? "מס רווח הון (25%)" :
            asset.tax_treatment === "tax_spread" ? `פריסת מס (${asset.spread_years || 0} שנים)` :
            asset.tax_treatment === "fixed_rate" ? `שיעור קבוע ${asset.tax_rate}%` :
            "לא מוגדר"
          }</div>
        </div>
        
        <div className="asset-item-actions">
          {asset.id && (
            <button
              type="button"
              onClick={() => onEdit(asset)}
              className="asset-item-edit-button"
            >
              ערוך
            </button>
          )}
          
          {asset.id && (
            <button
              type="button"
              onClick={() => onDelete(asset.id!)}
              className="asset-item-delete-button"
            >
              מחק
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
