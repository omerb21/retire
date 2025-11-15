import React from 'react';
import { useClients } from './hooks/useClients';
import { NewClientForm } from './components/NewClientForm';
import { ClientAddressSection } from './components/ClientAddressSection';
import { ClientExtraDataSection } from './components/ClientExtraDataSection';
import { ClientsMessageAlert } from './components/ClientsMessageAlert';
import { ClientsTable } from './components/ClientsTable';
import { EditClientModal } from './components/EditClientModal';

const ClientsPage: React.FC = () => {
  const {
    items,
    loading,
    form,
    setForm,
    msg,
    editingClient,
    editForm,
    setEditForm,
    deleteClient,
    startEdit,
    cancelEdit,
    saveEdit,
    onCreate
  } = useClients();

  return (
    <div>
      <div className="modern-card">
        <div className="card-header">
          <div>
            <h2 className="card-title">ניהול לקוחות</h2>
            <p className="card-subtitle">צפייה וניהול של כל הלקוחות במערכת</p>
          </div>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            gap: 16,
            alignItems: 'start'
          }}
        >
          <NewClientForm form={form} setForm={setForm} onSubmit={onCreate} />
          <ClientAddressSection form={form} setForm={setForm} />
          <ClientExtraDataSection form={form} setForm={setForm} />
        </div>

        <ClientsMessageAlert msg={msg} />

        <ClientsTable
          items={items}
          loading={loading}
          onStartEdit={startEdit}
          onDeleteClient={deleteClient}
        />

        <EditClientModal
          editingClient={editingClient}
          editForm={editForm}
          setEditForm={setEditForm}
          onSave={saveEdit}
          onCancel={cancelEdit}
        />
      </div>
    </div>
  );
};

export default ClientsPage;
