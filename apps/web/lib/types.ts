export type ConfidenceLevel = "live" | "cached" | "indicative" | "mock";

export type Flight = {
  id: string;
  origin: string;
  destination: string;
  departureDateTime: string;
  arrivalDateTime: string;
  airline: string;
  price: number;
  currency: string;
  bookingUrl?: string | null;
  deepLink?: string | null;
  affiliateUrl?: string | null;
  provider?: string;
  agentName?: string | null;
  stops?: number | null;
  durationMinutes?: number | null;
  isLive?: boolean;
  confidenceLevel?: ConfidenceLevel;
  observedAt?: string | null;
  expiresAt?: string | null;
};

export type GroundTransfer = {
  fromAirport: string;
  toAirport: string;
  fromCity: string;
  toCity: string;
  durationHours: number;
  estimatedCost: number;
  mode: string;
};

export type TripOption = {
  id: string;
  tripType: "same_city" | "open_jaw";
  outboundFlight: Flight;
  returnFlight: Flight;
  groundTransfer: GroundTransfer | null;
  totalPrice: number;
  tripLengthDays: number;
  nights: number;
  score: number;
  explanation: string;
  warnings: string[];
  tags: string[];
  bookingUrl?: string | null;
  bookingLabel?: string | null;
  affiliateUrl?: string | null;
  providerDeepLink?: string | null;
  outboundBookingUrl?: string | null;
  returnBookingUrl?: string | null;
  provider?: string | null;
  linkType?: "provider_deeplink" | "affiliate_referral" | "none";
};

export type TripStyle = "one city" | "two nearby cities" | "surprise me";

export type TripSearchPayload = {
  originAirports: string[];
  startDate: string;
  endDate: string;
  minTripLengthDays: number;
  maxTripLengthDays: number;
  maxBudget: number;
  maxGroundTransferHours: number;
  tripStyle: TripStyle;
  directOnly?: boolean;
  includeBaggage?: boolean;
};

export type ProviderMetadata = {
  providerUsed?: string | null;
  liveProviderAttempted?: boolean;
  liveProviderSucceeded?: boolean;
  cachedResultsUsed?: boolean;
  cachedResultsStale?: boolean;
  providerName?: string | null;
  requestsAttempted?: number | null;
  requestsLimit?: number | null;
  rawOffersCount?: number | null;
  mappedFlightsCount?: number | null;
  skippedOffersCount?: number | null;
  affiliateLinksGenerated?: number | null;
  deepLinksReturned?: number | null;
  providerWarnings?: string[];
};

export type TripSearchResponse = {
  trips: TripOption[];
  providerUsed?: string | null;
  providerWarnings?: string[];
  cachedResultsUsed?: boolean;
  providerMetadata?: ProviderMetadata | null;
};

export type AISearchResponse = {
  message: string;
  parsedRequest: TripSearchPayload | null;
  trips: TripOption[];
  missingFields: string[];
  confidence?: number | null;
  providerMetadata?: ProviderMetadata | null;
  aiMetadata: {
    aiProvider: string;
    model: string;
    toolCallsUsed: number;
    fallbackUsed: boolean;
    warnings: string[];
  };
};

export type AuthUser = {
  id: string;
  email: string;
  displayName?: string | null;
  isVerified: boolean;
  createdAt: string;
};

export type AuthResponse = {
  user: AuthUser;
  message: string;
};

export type SavedSearch = {
  id: string;
  email: string;
  name?: string | null;
  originAirports?: string[];
  startDate?: string;
  endDate?: string;
  minTripLengthDays?: number;
  maxTripLengthDays?: number;
  maxBudget?: number;
  tripStyle?: string;
  frequency?: string;
  isActive?: boolean;
  createdAt?: string;
  lastCheckedAt?: string | null;
  lastNotifiedAt?: string | null;
  lastBestPrice?: number | null;
  manageUrl?: string | null;
  unsubscribeUrl?: string | null;
};

export type TripType =
  | "weekend_city_break"
  | "beach"
  | "food"
  | "culture"
  | "nature"
  | "nightlife"
  | "cheap_adventure"
  | "long_haul_dream";

export type ComfortRule =
  | "direct_only"
  | "max_one_stop"
  | "avoid_overnight_layovers"
  | "no_departures_before_6am"
  | "no_returns_after_midnight"
  | "cabin_bag_included";

export type TravelProfile = {
  userId: string;
  isComplete: boolean;
  homeLocation?: string | null;
  originAirports: string[];
  maxAirportTravelTimeMinutes: number;
  preferredTripTypes: TripType[];
  preferredTripLengthMin: number;
  preferredTripLengthMax: number;
  budgetComfortZone: "under_100" | "under_200" | "under_400" | "flexible";
  spontaneity: "tomorrow" | "next_week" | "next_month" | "planning_ahead";
  comfortRules: ComfortRule[];
  openJawWillingness: "simple_returns_only" | "nearby_city_open_jaw" | "adventurous_multi_city";
  notificationFrequency: "instant_email" | "weekly_digest" | "urgent_only" | "push_later";
  excludedAirlines: string[];
  preferredMonths: number[];
  createdAt?: string | null;
  updatedAt?: string | null;
};

export type BillingStatus = {
  plan: string;
  subscriptionStatus?: string;
  billingEnabled?: boolean;
  usage?: Record<string, number>;
  limits?: Record<string, number | string>;
  [key: string]: unknown;
};

export type DashboardResponse = {
  user: AuthUser;
  billing: BillingStatus;
  usage: Record<string, number>;
  savedSearches: SavedSearch[];
  savedSearchSummary: { total: number; active: number };
};

export type ProviderStatusEntry = {
  name: string;
  accessStatus: "available" | "requires_approval" | "not_configured" | "disabled";
  enabled: boolean;
  configured: boolean;
  implementationStatus: "implemented" | "adapter_only" | "planned";
  capabilities: Record<string, boolean>;
  requiredEnvVars: string[];
  rateLimitNotes?: string | null;
  warnings: string[];
};

export type ProvidersStatusResponse = {
  configuredProvider: string;
  liveProvider: string;
  database: { available: boolean; cachedFlightsCount: number };
  providers: ProviderStatusEntry[];
  warnings: string[];
};
