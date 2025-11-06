import React from 'react';
import { Link } from 'react-router-dom';

interface ModuleLinkProps {
  to: string;
  label: string;
}

export const ModuleLink: React.FC<ModuleLinkProps> = ({ to, label }) => {
  return (
    <Link 
      to={to}
      style={{
        padding: '10px 15px',
        backgroundColor: '#f0f0f0',
        borderRadius: '4px',
        textDecoration: 'none',
        color: '#333',
        fontWeight: 'bold',
      }}
    >
      {label}
    </Link>
  );
};
