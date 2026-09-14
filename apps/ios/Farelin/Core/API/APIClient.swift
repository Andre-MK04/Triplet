import Foundation

struct HealthResponse: Decodable, Sendable {
    let status: String
}

enum APIError: LocalizedError, Sendable {
    case invalidResponse
    case unavailable
    case unauthorized
    case server(message: String, statusCode: Int)

    var errorDescription: String? {
        switch self {
        case .invalidResponse: "Farelin returned an unexpected response."
        case .unavailable: "Farelin could not be reached. Check your connection and try again."
        case .unauthorized: "Your session has expired. Please sign in again."
        case .server(let message, _): message
        }
    }
}

protocol NativeAuthServicing: Sendable {
    func legalVersions() async throws -> LegalVersions
    func nativeLogin(email: String, password: String) async throws -> NativeAuthTokens
    func nativeSignup(
        email: String,
        password: String,
        displayName: String?,
        legal: LegalVersions
    ) async throws -> NativeAuthTokens
    func nativeRefresh(refreshToken: String) async throws -> NativeAuthTokens
    func nativeLogout(refreshToken: String) async throws
    func currentUser() async throws -> AuthUser
    func requestVerificationCode() async throws -> VerificationDelivery
    func confirmVerificationCode(_ code: String) async throws -> AuthUser
    func setAccessToken(_ token: String?) async
}

actor APIClient: NativeAuthServicing, DashboardServicing, TravelProfileServicing {
    private let baseURL: URL
    private let session: URLSession
    private var accessToken: String?

    init(baseURL: URL, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.session = session
    }

    func health() async throws -> HealthResponse {
        try await send(path: "health", method: "GET", response: HealthResponse.self)
    }

    func dashboard() async throws -> DashboardResponse {
        try await send(
            path: "me/dashboard",
            method: "GET",
            authenticated: true,
            response: DashboardResponse.self
        )
    }

    func travelProfile() async throws -> TravelProfileResponse {
        try await send(
            path: "me/travel-profile",
            method: "GET",
            authenticated: true,
            response: TravelProfileResponse.self
        )
    }

    func updateTravelProfile(_ payload: TravelProfilePayload) async throws -> TravelProfileResponse {
        try await send(
            path: "me/travel-profile",
            method: "PUT",
            body: payload,
            authenticated: true,
            response: TravelProfileResponse.self
        )
    }

    func searchLocations(_ query: String) async throws -> [LocationResult] {
        try await send(
            path: "locations/search",
            method: "GET",
            queryItems: [URLQueryItem(name: "q", value: query)],
            response: [LocationResult].self
        )
    }

    func recommendedAirports(
        latitude: Double,
        longitude: Double,
        maxDistanceKm: Int
    ) async throws -> [AirportResult] {
        try await send(
            path: "airports/recommended",
            method: "GET",
            queryItems: [
                URLQueryItem(name: "lat", value: String(latitude)),
                URLQueryItem(name: "lon", value: String(longitude)),
                URLQueryItem(name: "maxDistanceKm", value: String(maxDistanceKm)),
                URLQueryItem(name: "originsOnly", value: "true"),
            ],
            response: [AirportResult].self
        )
    }

    func searchAirports(
        _ query: String,
        latitude: Double?,
        longitude: Double?
    ) async throws -> [AirportResult] {
        var queryItems = [
            URLQueryItem(name: "q", value: query),
            URLQueryItem(name: "originsOnly", value: "true"),
        ]
        if let latitude, let longitude {
            queryItems.append(URLQueryItem(name: "lat", value: String(latitude)))
            queryItems.append(URLQueryItem(name: "lon", value: String(longitude)))
        }
        return try await send(
            path: "airports/search",
            method: "GET",
            queryItems: queryItems,
            response: [AirportResult].self
        )
    }

    func setAccessToken(_ token: String?) {
        accessToken = token
    }

    func legalVersions() async throws -> LegalVersions {
        let response = try await send(path: "billing/plans", method: "GET", response: PlansEnvelope.self)
        return LegalVersions(termsVersion: response.termsVersion, privacyVersion: response.privacyVersion)
    }

    func nativeLogin(email: String, password: String) async throws -> NativeAuthTokens {
        try await send(
            path: "auth/native/login",
            method: "POST",
            body: LoginPayload(email: email, password: password),
            response: NativeAuthTokens.self
        )
    }

    func nativeSignup(
        email: String,
        password: String,
        displayName: String?,
        legal: LegalVersions
    ) async throws -> NativeAuthTokens {
        try await send(
            path: "auth/native/signup",
            method: "POST",
            body: SignupPayload(
                email: email,
                password: password,
                displayName: displayName,
                acceptedTermsVersion: legal.termsVersion,
                acknowledgedPrivacyVersion: legal.privacyVersion
            ),
            response: NativeAuthTokens.self
        )
    }

    func nativeRefresh(refreshToken: String) async throws -> NativeAuthTokens {
        try await send(
            path: "auth/native/refresh",
            method: "POST",
            body: RefreshPayload(refreshToken: refreshToken),
            response: NativeAuthTokens.self
        )
    }

    func nativeLogout(refreshToken: String) async throws {
        _ = try await send(
            path: "auth/native/logout",
            method: "POST",
            body: RefreshPayload(refreshToken: refreshToken),
            response: LogoutResponse.self
        )
    }

    func currentUser() async throws -> AuthUser {
        let response = try await send(
            path: "auth/me",
            method: "GET",
            authenticated: true,
            response: AuthEnvelope.self
        )
        return response.user
    }

    func requestVerificationCode() async throws -> VerificationDelivery {
        try await send(
            path: "auth/native/verify-email/request",
            method: "POST",
            authenticated: true,
            response: VerificationDelivery.self
        )
    }

    func confirmVerificationCode(_ code: String) async throws -> AuthUser {
        let response = try await send(
            path: "auth/native/verify-email/confirm",
            method: "POST",
            body: VerificationCodePayload(code: code),
            authenticated: true,
            response: AuthEnvelope.self
        )
        return response.user
    }

    private func send<Response: Decodable & Sendable>(
        path: String,
        method: String,
        queryItems: [URLQueryItem] = [],
        authenticated: Bool = false,
        response: Response.Type
    ) async throws -> Response {
        try await send(
            path: path,
            method: method,
            queryItems: queryItems,
            body: Optional<EmptyPayload>.none,
            authenticated: authenticated,
            response: response
        )
    }

    private func send<Body: Encodable & Sendable, Response: Decodable & Sendable>(
        path: String,
        method: String,
        queryItems: [URLQueryItem] = [],
        body: Body?,
        authenticated: Bool = false,
        response: Response.Type
    ) async throws -> Response {
        guard var components = URLComponents(
            url: baseURL.appending(path: path),
            resolvingAgainstBaseURL: false
        ) else {
            throw APIError.invalidResponse
        }
        if !queryItems.isEmpty {
            components.queryItems = queryItems
        }
        guard let url = components.url else { throw APIError.invalidResponse }
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.timeoutInterval = 20
        request.cachePolicy = .reloadIgnoringLocalCacheData
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if let body {
            request.httpBody = try JSONEncoder().encode(body)
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        if authenticated {
            guard let accessToken else { throw APIError.unauthorized }
            request.setValue("Bearer \(accessToken)", forHTTPHeaderField: "Authorization")
        }

        do {
            let (data, urlResponse) = try await session.data(for: request)
            guard let http = urlResponse as? HTTPURLResponse else {
                throw APIError.invalidResponse
            }
            if http.statusCode == 401 {
                throw APIError.unauthorized
            }
            guard (200 ..< 300).contains(http.statusCode) else {
                let detail = (try? JSONDecoder().decode(APIErrorEnvelope.self, from: data).detail)
                    ?? "Farelin could not complete that request."
                throw APIError.server(message: detail, statusCode: http.statusCode)
            }
            do {
                return try JSONDecoder().decode(Response.self, from: data)
            } catch {
                throw APIError.invalidResponse
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw APIError.unavailable
        }
    }
}

private struct EmptyPayload: Encodable, Sendable {}
private struct APIErrorEnvelope: Decodable, Sendable { let detail: String }
