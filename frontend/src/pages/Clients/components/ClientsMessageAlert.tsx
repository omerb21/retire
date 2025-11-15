import React from 'react';

interface ClientsMessageAlertProps {
  msg: string;
}

export const ClientsMessageAlert: React.FC<ClientsMessageAlertProps> = ({ msg }) => {
  if (!msg) {
    return null;
  }

  const isSuccess = msg.includes('✅');

  return (
    <div className={isSuccess ? 'alert alert-success' : 'alert alert-error'}>
      {msg}
    </div>
  );
};
