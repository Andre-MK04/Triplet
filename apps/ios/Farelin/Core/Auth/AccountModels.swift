import Foundation

protocol NativeAccountServicing: Sendable {
    func forgotPassword(email: String) async throws
    func resetPassword(token: String, password: String) async throws
    func changePassword(current: String, new: String) async throws
    func deleteAccount() async throws
    func exportAccount() async throws -> AccountExport
}

/// Structured JSON export, never logged or displayed inline.
indirect enum AccountExport: Codable, Sendable {
    case object([String: AccountExport]), array([AccountExport]), string(String)
    case number(Double), bool(Bool), null
    init(from decoder: any Decoder) throws {
        let c = try decoder.singleValueContainer()
        if c.decodeNil() { self = .null }
        else if let v = try? c.decode(Bool.self) { self = .bool(v) }
        else if let v = try? c.decode(Double.self) { self = .number(v) }
        else if let v = try? c.decode(String.self) { self = .string(v) }
        else if let v = try? c.decode([String: AccountExport].self) { self = .object(v) }
        else { self = .array(try c.decode([AccountExport].self)) }
    }
    func encode(to encoder: any Encoder) throws {
        var c = encoder.singleValueContainer()
        switch self {
        case .object(let v): try c.encode(v)
        case .array(let v): try c.encode(v)
        case .string(let v): try c.encode(v)
        case .number(let v): try c.encode(v)
        case .bool(let v): try c.encode(v)
        case .null: try c.encodeNil()
        }
    }
}
