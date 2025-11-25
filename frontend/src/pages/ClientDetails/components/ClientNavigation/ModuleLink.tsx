import React from 'react';
import { Link } from 'react-router-dom';
import styles from './ClientNavigation.module.css';

interface ModuleLinkProps {
  to: string;
  label: string;
}

export const ModuleLink: React.FC<ModuleLinkProps> = ({ to, label }) => {
  return (
    <Link 
      to={to}
      className={styles.moduleLink}
    >
      {label}
    </Link>
  );
};
