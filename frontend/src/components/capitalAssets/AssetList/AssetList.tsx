/**
 * AssetList Component
 * ===================
 * Component for displaying the list of capital assets
 */

import React from 'react';
import { CapitalAsset } from '../../../types/capitalAsset';
import { AssetItem } from './AssetItem';

interface AssetListProps {
  assets: CapitalAsset[];
  onEdit: (asset: CapitalAsset) => void;
  onDelete: (assetId: number) => void;
}

export function AssetList({ assets, onEdit, onDelete }: AssetListProps) {
  if (assets.length === 0) {
    return (
      <section>
        <h3>רשימת נכסי הון</h3>
        <div style={{ padding: 16, backgroundColor: "#f8f9fa", borderRadius: 4 }}>
          אין נכסי הון
        </div>
      </section>
    );
  }

  return (
    <section>
      <h3>רשימת נכסי הון</h3>
      <div style={{ display: "grid", gap: 16 }}>
        {assets.map((asset, index) => (
          <AssetItem
            key={asset.id || index}
            asset={asset}
            onEdit={onEdit}
            onDelete={onDelete}
          />
        ))}
      </div>
    </section>
  );
}
