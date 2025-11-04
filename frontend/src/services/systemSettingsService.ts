import { apiFetch } from "../lib/api";
import { SeveranceCap } from "../types/system-settings.types";

// Service for System Settings API calls

export const loadSeveranceCapsFromAPI = async (): Promise<SeveranceCap[]> => {
  try {
    const response = await apiFetch<{caps: SeveranceCap[]}>('/api/v1/tax-data/severance-caps');
    if (response && response.caps) {
      return response.caps;
    }
    throw new Error('No caps data received');
  } catch (error) {
    console.error("API error loading severance caps:", error);
    throw error;
  }
};

export const saveSeveranceCapsToAPI = async (caps: SeveranceCap[]): Promise<void> => {
  try {
    await apiFetch('/tax-data/severance-caps', {
      method: 'POST',
      body: JSON.stringify(caps),
    });
  } catch (error) {
    console.error("Error saving severance caps:", error);
    throw error;
  }
};

export const getDefaultSeveranceCaps = (): SeveranceCap[] => {
  return [
    {year: 2025, monthly_cap: 13750, annual_cap: 13750 * 12, description: 'תקרה חודשית לשנת 2025'},
    {year: 2024, monthly_cap: 13750, annual_cap: 13750 * 12, description: 'תקרה חודשית לשנת 2024'},
    {year: 2023, monthly_cap: 13310, annual_cap: 13310 * 12, description: 'תקרה חודשית לשנת 2023'},
    {year: 2022, monthly_cap: 12640, annual_cap: 12640 * 12, description: 'תקרה חודשית לשנת 2022'},
    {year: 2021, monthly_cap: 12340, annual_cap: 12340 * 12, description: 'תקרה חודשית לשנת 2021'},
    {year: 2020, monthly_cap: 12420, annual_cap: 12420 * 12, description: 'תקרה חודשית לשנת 2020'},
    {year: 2019, monthly_cap: 12380, annual_cap: 12380 * 12, description: 'תקרה חודשית לשנת 2019'},
    {year: 2018, monthly_cap: 12230, annual_cap: 12230 * 12, description: 'תקרה חודשית לשנת 2018'},
    {year: 2017, monthly_cap: 12200, annual_cap: 12200 * 12, description: 'תקרה חודשית לשנת 2017'},
    {year: 2016, monthly_cap: 12230, annual_cap: 12230 * 12, description: 'תקרה חודשית לשנת 2016'},
    {year: 2015, monthly_cap: 12340, annual_cap: 12340 * 12, description: 'תקרה חודשית לשנת 2015'},
    {year: 2014, monthly_cap: 12360, annual_cap: 12360 * 12, description: 'תקרה חודשית לשנת 2014'},
    {year: 2013, monthly_cap: 12120, annual_cap: 12120 * 12, description: 'תקרה חודשית לשנת 2013'},
    {year: 2012, monthly_cap: 11950, annual_cap: 11950 * 12, description: 'תקרה חודשית לשנת 2012'},
    {year: 2011, monthly_cap: 11650, annual_cap: 11650 * 12, description: 'תקרה חודשית לשנת 2011'},
    {year: 2010, monthly_cap: 11390, annual_cap: 11390 * 12, description: 'תקרה חודשית לשנת 2010'},
  ];
};
