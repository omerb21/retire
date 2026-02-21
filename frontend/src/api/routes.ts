export const apiRoutes = {
  clients: {
    byId: (clientId: string | number) => `/clients/${clientId}`,

    capitalAssets: (clientId: string | number) => `/clients/${clientId}/capital-assets`,
    capitalAssetById: (clientId: string | number, assetId: string | number) =>
      `/clients/${clientId}/capital-assets/${assetId}`,

    pensionFunds: (clientId: string | number) => `/clients/${clientId}/pension-funds`,
    pensionFundById: (clientId: string | number, fundId: string | number) =>
      `/clients/${clientId}/pension-funds/${fundId}`,
    pensionFundCompute: (clientId: string | number, fundId: string | number) =>
      `/clients/${clientId}/pension-funds/${fundId}/compute`,

    additionalIncomes: (clientId: string | number) => `/clients/${clientId}/additional-incomes`,
    additionalIncomeById: (clientId: string | number, incomeId: string | number) =>
      `/clients/${clientId}/additional-incomes/${incomeId}`,
  },
} as const;
