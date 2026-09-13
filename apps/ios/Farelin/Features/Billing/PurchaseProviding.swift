import Foundation

struct PurchaseProduct: Equatable, Sendable {
    let id: String
    let displayName: String
    let displayPrice: String
}

protocol PurchaseProviding: Sendable {
    func products() async throws -> [PurchaseProduct]
    func purchase(productID: String) async throws
    func restore() async throws
}

/// The launch app deliberately exposes no purchase path. A StoreKit 2 provider
/// can replace this implementation later without making the UI authoritative
/// for entitlements; the backend remains the source of truth.
struct DisabledPurchaseProvider: PurchaseProviding {
    func products() async throws -> [PurchaseProduct] { [] }
    func purchase(productID: String) async throws {}
    func restore() async throws {}
}

