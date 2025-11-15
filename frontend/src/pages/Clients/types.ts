export interface NewClientForm {
  id_number: string;
  first_name: string;
  last_name: string;
  birth_date: string;
  gender: string;
  email: string;
  phone: string;
  address_street: string;
  address_city: string;
  address_postal_code: string;
  pension_start_date: string;
  tax_credit_points: number;
  marital_status: string;
}

export interface EditClientForm {
  id_number: string;
  first_name: string;
  last_name: string;
  birth_date: string;
  gender: string;
  email: string;
  phone: string;
  address_street: string;
  address_city: string;
  address_postal_code: string;
  pension_start_date: string;
  tax_credit_points: number;
  marital_status: string;
}
