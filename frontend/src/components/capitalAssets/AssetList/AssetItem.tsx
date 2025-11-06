/**
 * AssetItem Component
 * ===================
 * Component for displaying a single capital asset item
 */

import React from 'react';
import { CapitalAsset, ASSET_TYPES } from '../../../types/capitalAsset';
import { formatDateToDDMMYY } from '../../../utils/dateUtils';

interface AssetItemProps {
  asset: CapitalAsset;
  onEdit: (asset: CapitalAsset) => void;
  onDelete: (assetId: number) => void;
}

export function AssetItem({ asset, onEdit, onDelete }: AssetItemProps) {
  return (
    <div style={{ padding: 16, border: "1px solid #ddd", borderRadius: 4, backgroundColor: "#f9f9f9" }}>
      <div style={{ display: "grid", gap: 8 }}>
        <div style={{ fontSize: "18px", fontWeight: "bold", color: "#0056b3", marginBottom: "8px" }}>
          {asset.asset_name || asset.description || "נכס ללא שם"}
        </div>
        
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
          <div style={{ backgroundColor: "#fff", padding: "8px", borderRadius: "4px", border: "1px solid #eee" }}>
            <div style={{ fontWeight: "bold", marginBottom: "4px" }}>פרטי נכס</div>
            <div><strong>סוג נכס:</strong> {ASSET_TYPES.find(t => t.value === asset.asset_type)?.label || asset.asset_type}</div>
            <div><strong>תשלום:</strong> ₪{(asset.monthly_income || 0).toLocaleString()}</div>
            <div><strong>ערך נוכחי:</strong> ₪{asset.current_value?.toLocaleString() || 0}</div>
            <div><strong>תשואה שנתית:</strong> {
              asset.annual_return_rate > 1 ? asset.annual_return_rate : 
              asset.annual_return_rate ? (asset.annual_return_rate * 100) : 
              asset.annual_return || 0
            }%</div>
          </div>
          
          <div style={{ backgroundColor: "#fff", padding: "8px", borderRadius: "4px", border: "1px solid #eee" }}>
            <div style={{ fontWeight: "bold", marginBottom: "4px" }}>תאריך ומס</div>
            <div><strong>תאריך תשלום:</strong> {asset.start_date ? formatDateToDDMMYY(new Date(asset.start_date)) : "לא צוין"}</div>
            <div><strong>הצמדה:</strong> {
              asset.indexation_method === "none" ? "ללא" :
              asset.indexation_method === "fixed" ? `קבועה ${asset.fixed_rate}%` :
              "למדד"
            }</div>
          </div>
        </div>
        
        <div style={{ backgroundColor: "#f0f8ff", padding: "8px", borderRadius: "4px", border: "1px solid #d1e7ff" }}>
          <div style={{ fontWeight: "bold", marginBottom: "4px" }}>מיסוי</div>
          <div><strong>יחס מס:</strong> {
            asset.tax_treatment === "exempt" ? "פטור ממס" :
            asset.tax_treatment === "taxable" ? "חייב במס רגיל" :
            asset.tax_treatment === "capital_gains" ? "מס רווח הון (25%)" :
            asset.tax_treatment === "tax_spread" ? `פריסת מס (${asset.spread_years || 0} שנים)` :
            asset.tax_treatment === "fixed_rate" ? `שיעור קבוע ${asset.tax_rate}%` :
            "לא מוגדר"
          }</div>
        </div>
        
        <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
          {asset.id && (
            <button
              type="button"
              onClick={() => onEdit(asset)}
              style={{ padding: "8px 12px", backgroundColor: "#007bff", color: "white", border: "none", borderRadius: 4 }}
            >
              ערוך
            </button>
          )}
          
          {asset.id && (
            <button
              type="button"
              onClick={() => onDelete(asset.id!)}
              style={{ padding: "8px 12px", backgroundColor: "#dc3545", color: "white", border: "none", borderRadius: 4 }}
            >
              מחק
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
