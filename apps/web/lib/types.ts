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

export type TripSegment = {
  kind: "flight" | "ground";
  origin: string;
  destination: string;
  originCity: string;
  destinationCity: string;
  departureDate: string;
  flight?: Flight | null;
  transfer?: GroundTransfer | null;
};

export type CityStay = {
  code: string;
  city: string;
  country: string;
  countryCode: string;
  arrivalDate: string;
  departureDate: string;
  nights: number;
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

export type ScoreComponent = {
  label: string;
  points: number;
};

export type TripOption = {
  id: string;
  tripType: "same_city" | "open_jaw" | "multi_city";
  outboundFlight: Flight;
  returnFlight: Flight;
  groundTransfer: GroundTransfer | null;
  segments?: TripSegment[];
  stays?: CityStay[];
  /** Sum of every flight fare — this is what totalPrice reports. */
  flightCost?: number;
  /** Rough cost of overland hops, for planning only. Never in totalPrice. */
  groundEstimate?: number | null;
  totalPrice: number;
  tripLengthDays: number;
  nights: number;
  score: number;
  dealScore?: number;
  fitScore?: number | null;
  dealScoreBreakdown?: ScoreComponent[];
  fitScoreBreakdown?: ScoreComponent[];
  suggestionId?: string | null;
  fareKind?: "two_one_ways" | "round_trip_bundle";
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
  destination?: {
    code: string;
    kind: "airport" | "city";
    city: string;
    country: string;
    countryCode: string;
    continent?: string | null;
  } | null;
};

export type TripStyle = "one city" | "two nearby cities" | "surprise me";

/** The shape of the trip: out and back, a chain of cities, or in one / out another. */
export type TripPlan = "return" | "multi_city" | "open_jaw";

export type TripSearchPayload = {
  originAirports: string[];
  destinationAirports?: string[] | null;
  destinationCountries?: string[];
  destinationRegions?: string[];
  destinationContinents?: string[];
  excludeEurope?: boolean;
  unvisitedOnly?: boolean;
  /** Multi-city: airports the traveller flies home from, when different from the destination. */
  returnOriginAirports?: string[] | null;
  startDate: string;
  endDate: string;
  minTripLengthDays: number;
  maxTripLengthDays: number;
  maxBudget: number;
  maxGroundTransferHours: number;
  tripStyle: TripStyle;
  tripPlan?: TripPlan;
  /** Ordered cities for a multi-city itinerary. */
  routeStops?: string[] | null;
  directOnly?: boolean;
  includeBaggage?: boolean;
};

export type FlightPlaceResult = {
  code: string;
  kind: "airport" | "city" | "country" | "region" | "continent";
  name: string;
  subtitle: string;
  city?: string | null;
  countryCode?: string | null;
  countryName?: string | null;
  continent?: string | null;
  searchCodes: string[];
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
  /** Set when nothing matched exactly and the closest real fares are shown instead. */
  relaxationNote?: string | null;
  providerUsed?: string | null;
  providerWarnings?: string[];
  cachedResultsUsed?: boolean;
  providerMetadata?: ProviderMetadata | null;
};

export type AISearchResponse = {
  message: string;
  parsedRequest: TripSearchPayload | null;
  trips: TripOption[];
  relaxationNote?: string | null;
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
  spontaneity:
    | "very_spontaneous"
    | "soon"
    | "flexible_monthly"
    | "planner"
    | "long_term_planner"
    | "tomorrow"
    | "next_week"
    | "next_month"
    | "planning_ahead";
  comfortRules: ComfortRule[];
  openJawWillingness: "simple_returns_only" | "nearby_city_open_jaw" | "adventurous_multi_city";
  notificationFrequency: "instant_email" | "weekly_digest" | "urgent_only" | "push_later";
  excludedAirlines: string[];
  preferredMonths: number[];
  // Profile v2 (all optional; sent back to /me/travel-profile).
  baseLocationId?: number | null;
  baseLatitude?: number | null;
  baseLongitude?: number | null;
  maxAirportDistanceKm?: number | null;
  recommendedOriginAirports?: string[];
  dealSensitivity?: "strict" | "balanced" | "flexible";
  absoluteMaxBudget?: number | null;
  alertTriggerMode?: "below_budget" | "route_deal" | "price_drop" | "any";
  comfortRuleModes?: Record<string, "off" | "prefer" | "require">;
  themePreference?: "light" | "dark" | "system" | null;
  createdAt?: string | null;
  updatedAt?: string | null;
};

export type LocationResult = {
  id: number;
  name: string;
  countryCode: string;
  countryName: string;
  adminRegion?: string | null;
  latitude: number;
  longitude: number;
  population?: number | null;
};

export type AirportResult = {
  iataCode: string;
  name: string;
  city?: string | null;
  countryCode: string;
  countryName: string;
  latitude: number;
  longitude: number;
  type: string;
  scheduledService: boolean;
  distanceKm?: number | null;
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

export type CountryCatalogEntry = {
  code: string;
  alpha3: string;
  numericCode: string;
  name: string;
  continent: string;
  countsTowardWorldTotal: boolean;
};

export type CountryCatalogResponse = {
  definition: string;
  worldTotal: number;
  continentTotal: number;
  continents: string[];
  countries: CountryCatalogEntry[];
};

export type TravelMapStatus = "visited" | "lived" | "wishlist" | "unvisited";
export type TravelDatePrecision = "exact" | "month" | "year" | "unknown";

export type CountryVisit = {
  id: string;
  countryCode: string;
  kind: "visit" | "lived";
  startDate: string | null;
  endDate: string | null;
  startPrecision: TravelDatePrecision;
  endPrecision: TravelDatePrecision;
  note: string | null;
  tripId: string | null;
  createdAt: string;
  updatedAt: string;
};

export type TravelMapCountry = {
  code: string;
  name: string;
  continent: string;
  visited: boolean;
  lived: boolean;
  wishlist: boolean;
  primaryStatus: TravelMapStatus;
  visitCount: number;
  residenceCount: number;
  visits: CountryVisit[];
  updatedAt: string;
};

export type ContinentProgress = { name: string; visited: number; total: number };

export type TravelMapResponse = {
  countries: TravelMapCountry[];
  stats: {
    countriesVisited: number;
    countriesLivedIn: number;
    wishlistCountries: number;
    worldTotal: number;
    worldExploredPercentage: number;
    continentsVisited: number;
    continentTotal: number;
    continentProgress: ContinentProgress[];
  };
  updatedAt: string | null;
};

export type ItineraryItem = {
  partOfDay: "morning" | "afternoon" | "evening" | "flexible";
  title: string;
  description: string;
  category: string;
  estimatedCost: string;
};

export type ItineraryDay = {
  label: string;
  items: ItineraryItem[];
};

export type ItineraryPlan = {
  summary: string;
  days: ItineraryDay[];
  gettingAround?: string | null;
  extraCostEstimate?: string | null;
  disclaimers: string[];
  generatedAt?: string | null;
};

export type ItineraryResponse = {
  itinerary: ItineraryPlan;
  cached: boolean;
};

export type TripSuggestionResponse = {
  id: string;
  title: string;
  tripType: string;
  createdAt: string;
  expiresAt?: string | null;
  dealScore: number;
  fitScore?: number | null;
  trip: TripOption;
  itinerary?: ItineraryPlan | null;
  disclaimer: string;
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
