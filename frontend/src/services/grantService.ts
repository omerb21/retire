/**
 * Grant Service - API calls for grants
 * שירות למענקים - קריאות API
 */

import axios from 'axios';
import { API_BASE } from '../lib/api';
import { Grant, GrantFormData } from '../types/grant.types';
import { convertDDMMYYToISO } from '../utils/dateUtils';

export class GrantService {
  /**
   * Fetch all grants for a client
   */
  static async fetchGrants(clientId: string): Promise<Grant[]> {
    try {
      const response = await axios.get(`${API_BASE}/clients/${clientId}/grants`);
      const grantsData = response.data || [];
      
      // התאמת שדות - סנכרון בין amount ו-grant_amount
      return grantsData.map((grant: Grant) => {
        if (grant.amount !== undefined && grant.grant_amount === undefined) {
          grant.grant_amount = grant.amount;
        }
        if (grant.grant_amount !== undefined && grant.amount === undefined) {
          grant.amount = grant.grant_amount;
        }
        return grant;
      });
    } catch (error) {
      console.error('Error loading grants:', error);
      throw new Error('שגיאה בטעינת המענקים');
    }
  }

  /**
   * Create a new grant
   */
  static async createGrant(clientId: string, grantData: GrantFormData): Promise<void> {
    // Validate required fields
    if (!grantData.employer_name || !grantData.work_start_date || !grantData.work_end_date || 
        !grantData.grant_date || (grantData.grant_amount || 0) <= 0) {
      throw new Error('יש למלא את כל השדות הנדרשים');
    }

    // Convert dates to ISO format
    const workStartDateISO = convertDDMMYYToISO(grantData.work_start_date);
    const workEndDateISO = convertDDMMYYToISO(grantData.work_end_date);
    const grantDateISO = convertDDMMYYToISO(grantData.grant_date);
    
    if (!workStartDateISO || !workEndDateISO || !grantDateISO) {
      throw new Error('תאריכים לא תקינים - יש להזין בפורמט DD/MM/YYYY');
    }

    try {
      await axios.post(`${API_BASE}/clients/${clientId}/grants`, {
        ...grantData,
        work_start_date: workStartDateISO,
        work_end_date: workEndDateISO,
        grant_date: grantDateISO
      });
    } catch (error: any) {
      console.error('Error creating grant:', error);
      throw new Error('שגיאה בהוספת מענק: ' + (error.message || 'שגיאה לא ידועה'));
    }
  }

  /**
   * Delete a grant
   */
  static async deleteGrant(clientId: string, grantId: number): Promise<void> {
    try {
      await axios.delete(`${API_BASE}/clients/${clientId}/grants/${grantId}`);
    } catch (error: any) {
      console.error('Error deleting grant:', error);
      throw new Error('שגיאה במחיקת מענק: ' + (error.message || 'שגיאה לא ידועה'));
    }
  }

  /**
   * Get severance exemption from API
   */
  static async getSeveranceExemption(serviceYears: number): Promise<number> {
    try {
      const response = await axios.get(`${API_BASE}/tax-data/severance-exemption`, {
        params: { service_years: serviceYears }
      });
      return response.data.total_exemption;
    } catch (error) {
      console.error('Error fetching tax data:', error);
      // Fallback: תקרה חודשית לשנת 2025 (13,750 ₪) × 12 חודשים × שנות ותק
      // NOTE: ערך זה צריך להתעדכן מדי שנה או להיטען מהשרת
      const monthlyCap2025 = 13750;
      const annualCap = monthlyCap2025 * 12;
      return annualCap * serviceYears;
    }
  }
}
