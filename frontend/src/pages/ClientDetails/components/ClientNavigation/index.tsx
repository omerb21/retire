import React from 'react';
import { Link } from 'react-router-dom';
import styles from './ClientNavigation.module.css';

interface ClientNavigationProps {
  clientId: string;
}

export const ClientNavigation: React.FC<ClientNavigationProps> = ({ clientId }) => {
  return (
    <div>
      <div className={styles.navigationContainer}>
        <Link to={`/clients/${clientId}/pension-portfolio`} className={styles.moduleButton}>
          תיק פנסיוני
        </Link>
        <Link to={`/clients/${clientId}/grants`} className={styles.moduleButton}>
          מענקים פטורים
        </Link>
        <Link to={`/clients/${clientId}/current-employer`} className={styles.moduleButton}>
          מעסיק נוכחי
        </Link>
        <Link to={`/clients/${clientId}/pension-funds`} className={styles.moduleButton}>
          קצבאות והיוונים
        </Link>
        <Link to={`/clients/${clientId}/additional-incomes`} className={styles.moduleButton}>
          הכנסות נוספות
        </Link>
        <Link to={`/clients/${clientId}/capital-assets`} className={styles.moduleButton}>
          נכסי הון
        </Link>
        <Link to={`/clients/${clientId}/fixation`} className={styles.moduleButton}>
          קיבוע זכויות
        </Link>
        <Link to={`/clients/${clientId}/reports`} className={styles.moduleButton}>
          📊 תוצאות
        </Link>
        <Link to={`/clients/${clientId}/retirement-scenarios`} className={styles.moduleButton}>
          🎯 תרחישים
        </Link>
        <Link to={`/clients/${clientId}/llm-chat`} className={styles.moduleButton}>
          🤖 יועץ פרישה
        </Link>
      </div>

 
    </div>
  );
};
