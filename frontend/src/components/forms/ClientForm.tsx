import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createClient, ClientItem } from '../../lib/api';
import DateField from './DateField';

interface ClientFormProps {
  onSuccess?: (clientId: number) => void;
}

interface ClientFormData {
  id_number: string;
  first_name: string;
  last_name: string;
  birth_date: string;
  email?: string | null;
  phone?: string | null;
  retirement_date?: string | null;
  gender?: string | null;
  marital_status?: string | null;
  
  // Address fields
  address_street?: string | null;
  address_city?: string | null;
  address_postal_code?: string | null;
  
  // Tax-related fields
  num_children: number;
  is_new_immigrant: boolean;
  is_veteran: boolean;
  is_disabled: boolean;
  disability_percentage?: number | null;
  is_student: boolean;
  reserve_duty_days: number;
  
  // Income and deductions
  annual_salary?: number | null;
  pension_contributions: number;
  study_fund_contributions: number;
  insurance_premiums: number;
  charitable_donations: number;
  
  // Tax credit points
  tax_credit_points: number;
  // pension_start_date נמחק לפי דרישה
  spouse_income?: number | null;
  immigration_date?: string | null;
  military_discharge_date?: string | null;
}

const ClientForm: React.FC<ClientFormProps> = ({ onSuccess }) => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState<ClientFormData>({
    first_name: '',
    last_name: '',
    id_number: '',
    birth_date: '',
    gender: null,
    marital_status: null,
    
    // Address fields
    address_street: null,
    address_city: null,
    address_postal_code: null,
    
    // Tax-related fields
    num_children: 0,
    is_new_immigrant: false,
    is_veteran: false,
    is_disabled: false,
    disability_percentage: null,
    is_student: false,
    reserve_duty_days: 0,
    
    // Income and deductions
    annual_salary: null,
    pension_contributions: 0,
    study_fund_contributions: 0,
    insurance_premiums: 0,
    charitable_donations: 0,
    
    // Tax credit points
    tax_credit_points: 0,
    // pension_start_date נמחק לפי דרישה
    spouse_income: null,
    immigration_date: null,
    military_discharge_date: null,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value, type } = e.target;
    let parsedValue: any = value;
    
    if (type === 'number') {
      parsedValue = value === '' ? null : Number(value);
    } else if (type === 'checkbox') {
      parsedValue = (e.target as HTMLInputElement).checked;
    }
    
    setFormData(prev => ({
      ...prev,
      [name]: parsedValue
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      // Use the createClient function from our updated API utilities
      const newClient = await createClient({
        first_name: formData.first_name.trim(),
        last_name: formData.last_name.trim(),
        id_number: formData.id_number.trim(),
        birth_date: formData.birth_date,
        email: formData.email || null,
        phone: formData.phone || null,
        gender: formData.gender || undefined,
        marital_status: formData.marital_status || undefined,
        
        // Address fields
        address_street: formData.address_street || undefined,
        address_city: formData.address_city || undefined,
        address_postal_code: formData.address_postal_code || undefined,
        
        // Tax-related fields
        num_children: formData.num_children,
        is_new_immigrant: formData.is_new_immigrant,
        is_veteran: formData.is_veteran,
        is_disabled: formData.is_disabled,
        disability_percentage: formData.disability_percentage,
        is_student: formData.is_student,
        reserve_duty_days: formData.reserve_duty_days,
        
        // Income and deductions
        annual_salary: formData.annual_salary,
        pension_contributions: formData.pension_contributions,
        study_fund_contributions: formData.study_fund_contributions,
        insurance_premiums: formData.insurance_premiums,
        charitable_donations: formData.charitable_donations,
        
        // Tax credit points
        tax_credit_points: formData.tax_credit_points,
        // pension_start_date נמחק לפי דרישה
        spouse_income: formData.spouse_income,
        immigration_date: formData.immigration_date,
        military_discharge_date: formData.military_discharge_date,
      });
      
      if (onSuccess && newClient.id) {
        onSuccess(newClient.id);
      } else if (newClient.id) {
        navigate(`/clients/${newClient.id}`);
      }
    } catch (err: any) {
      // Error message is now correctly formatted by our API utility
      setError(`כשל בשמירה: ${err.message || "שגיאה לא מוכרת"}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      )}

      <div>
        <label className="block text-sm font-medium mb-1">
          שם פרטי *
          <input
            type="text"
            name="first_name"
            value={formData.first_name || ''}
            onChange={handleChange}
            required
            className="mt-1 block w-full border rounded-md shadow-sm py-2 px-3"
          />
        </label>
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">
          שם משפחה *
          <input
            type="text"
            name="last_name"
            value={formData.last_name || ''}
            onChange={handleChange}
            required
            className="mt-1 block w-full border rounded-md shadow-sm py-2 px-3"
          />
        </label>
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">
          מספר זהות *
          <input
            type="text"
            name="id_number"
            value={formData.id_number}
            onChange={handleChange}
            required
            className="mt-1 block w-full border rounded-md shadow-sm py-2 px-3"
          />
        </label>
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">
          תאריך לידה *
          <DateField
            label=""
            value={formData.birth_date || null}
            onChange={(newValue) =>
              setFormData((prev) => ({
                ...prev,
                birth_date: newValue || '',
              }))
            }
            required
          />
        </label>
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">
          אימייל
          <input
            type="email"
            name="email"
            value={formData.email || ''}
            onChange={handleChange}
            className="mt-1 block w-full border rounded-md shadow-sm py-2 px-3"
          />
        </label>
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">
          טלפון
          <input
            type="tel"
            name="phone"
            value={formData.phone || ''}
            onChange={handleChange}
            className="mt-1 block w-full border rounded-md shadow-sm py-2 px-3"
          />
        </label>
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">
          תאריך פרישה צפוי
          <DateField
            label=""
            value={formData.retirement_date || null}
            onChange={(newValue) =>
              setFormData((prev) => ({
                ...prev,
                retirement_date: newValue || null,
              }))
            }
          />
        </label>
      </div>

      {/* Address Fields */}
      <div className="border-t pt-4 mt-6">
        <h3 className="text-lg font-medium mb-4">כתובת</h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1">
              רחוב
              <input
                type="text"
                name="address_street"
                value={formData.address_street || ''}
                onChange={handleChange}
                className="mt-1 block w-full border rounded-md shadow-sm py-2 px-3"
              />
            </label>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              עיר
              <input
                type="text"
                name="address_city"
                value={formData.address_city || ''}
                onChange={handleChange}
                className="mt-1 block w-full border rounded-md shadow-sm py-2 px-3"
              />
            </label>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              מיקוד
              <input
                type="text"
                name="address_postal_code"
                value={formData.address_postal_code || ''}
                onChange={handleChange}
                className="mt-1 block w-full border rounded-md shadow-sm py-2 px-3"
              />
            </label>
          </div>
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">
          מין
          <select
            name="gender"
            value={formData.gender || ''}
            onChange={handleChange}
            className="mt-1 block w-full border rounded-md shadow-sm py-2 px-3"
          >
            <option value="">בחר מין</option>
            <option value="male">זכר</option>
            <option value="female">נקבה</option>
          </select>
        </label>
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">
          מצב משפחתי
          <select
            name="marital_status"
            value={formData.marital_status || ''}
            onChange={handleChange}
            className="mt-1 block w-full border rounded-md shadow-sm py-2 px-3"
          >
            <option value="">בחר מצב משפחתי</option>
            <option value="single">רווק/ה</option>
            <option value="married">נשוי/ה</option>
            <option value="divorced">גרוש/ה</option>
            <option value="widowed">אלמן/ה</option>
          </select>
        </label>
      </div>

      {/* Tax-related fields section */}
      <div className="border-t pt-4 mt-6">
        <h3 className="text-lg font-medium mb-4">פרטים למיסוי</h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1">
              מספר ילדים
              <input
                type="number"
                name="num_children"
                value={formData.num_children}
                onChange={handleChange}
                min="0"
                className="mt-1 block w-full border rounded-md shadow-sm py-2 px-3"
              />
            </label>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              ימי מילואים בשנה
              <input
                type="number"
                name="reserve_duty_days"
                value={formData.reserve_duty_days}
                onChange={handleChange}
                min="0"
                className="mt-1 block w-full border rounded-md shadow-sm py-2 px-3"
              />
            </label>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              אחוז נכות (%)
              <input
                type="number"
                name="disability_percentage"
                value={formData.disability_percentage || ''}
                onChange={handleChange}
                min="0"
                max="100"
                className="mt-1 block w-full border rounded-md shadow-sm py-2 px-3"
              />
            </label>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              נקודות זיכוי במס (ידני)
              <input
                type="number"
                name="tax_credit_points"
                value={formData.tax_credit_points}
                onChange={handleChange}
                min="0"
                step="0.1"
                className="mt-1 block w-full border rounded-md shadow-sm py-2 px-3"
              />
            </label>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
          <div className="flex items-center">
            <input
              type="checkbox"
              name="is_new_immigrant"
              checked={formData.is_new_immigrant}
              onChange={handleChange}
              className="mr-2"
            />
            <label className="text-sm font-medium">עולה חדש</label>
          </div>

          <div className="flex items-center">
            <input
              type="checkbox"
              name="is_veteran"
              checked={formData.is_veteran}
              onChange={handleChange}
              className="mr-2"
            />
            <label className="text-sm font-medium">חייל משוחרר</label>
          </div>

          <div className="flex items-center">
            <input
              type="checkbox"
              name="is_disabled"
              checked={formData.is_disabled}
              onChange={handleChange}
              className="mr-2"
            />
            <label className="text-sm font-medium">נכה</label>
          </div>

          <div className="flex items-center">
            <input
              type="checkbox"
              name="is_student"
              checked={formData.is_student}
              onChange={handleChange}
              className="mr-2"
            />
            <label className="text-sm font-medium">סטודנט</label>
          </div>
        </div>
      </div>

      {/* Income and deductions section */}
      <div className="border-t pt-4 mt-6">
        <h3 className="text-lg font-medium mb-4">הכנסות וניכויים</h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1">
              שכר שנתי (₪)
              <input
                type="number"
                name="annual_salary"
                value={formData.annual_salary || ''}
                onChange={handleChange}
                min="0"
                className="mt-1 block w-full border rounded-md shadow-sm py-2 px-3"
              />
            </label>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              הכנסת בן/בת זוג (₪)
              <input
                type="number"
                name="spouse_income"
                value={formData.spouse_income || ''}
                onChange={handleChange}
                min="0"
                className="mt-1 block w-full border rounded-md shadow-sm py-2 px-3"
              />
            </label>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              הפרשות לפנסיה (₪)
              <input
                type="number"
                name="pension_contributions"
                value={formData.pension_contributions}
                onChange={handleChange}
                min="0"
                className="mt-1 block w-full border rounded-md shadow-sm py-2 px-3"
              />
            </label>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              הפרשות לקרן השתלמות (₪)
              <input
                type="number"
                name="study_fund_contributions"
                value={formData.study_fund_contributions}
                onChange={handleChange}
                min="0"
                className="mt-1 block w-full border rounded-md shadow-sm py-2 px-3"
              />
            </label>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              דמי ביטוח (₪)
              <input
                type="number"
                name="insurance_premiums"
                value={formData.insurance_premiums}
                onChange={handleChange}
                min="0"
                className="mt-1 block w-full border rounded-md shadow-sm py-2 px-3"
              />
            </label>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              תרומות (₪)
              <input
                type="number"
                name="charitable_donations"
                value={formData.charitable_donations}
                onChange={handleChange}
                min="0"
                className="mt-1 block w-full border rounded-md shadow-sm py-2 px-3"
              />
            </label>
          </div>
        </div>
      </div>

      {/* Important dates section */}
      <div className="border-t pt-4 mt-6">
        <h3 className="text-lg font-medium mb-4">תאריכים חשובים</h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* שדה תאריך תחילת קבלת פנסיה הוסר לפי דרישה */}

          <div>
            <label className="block text-sm font-medium mb-1">
              תאריך עלייה (לעולים חדשים)
              <DateField
                label=""
                value={formData.immigration_date || null}
                onChange={(newValue) =>
                  setFormData((prev) => ({
                    ...prev,
                    immigration_date: newValue || null,
                  }))
                }
              />
            </label>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              תאריך שחרור מצה"ל
              <DateField
                label=""
                value={formData.military_discharge_date || null}
                onChange={(newValue) =>
                  setFormData((prev) => ({
                    ...prev,
                    military_discharge_date: newValue || null,
                  }))
                }
              />
            </label>
          </div>
        </div>
      </div>

      <div className="flex justify-end space-x-2">
        <button
          type="button"
          onClick={() => navigate('/clients')}
          className="px-4 py-2 border rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
        >
          ביטול
        </button>
        <button
          type="submit"
          disabled={loading}
          className="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
        >
          {loading ? 'שומר...' : 'שמירה'}
        </button>
      </div>
    </form>
  );
};

export default ClientForm;
