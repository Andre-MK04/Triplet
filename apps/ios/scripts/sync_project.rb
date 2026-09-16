#!/usr/bin/env ruby
# Add source/resources without recreating the project or losing signing/user settings.
require "xcodeproj"
root = File.expand_path("..", __dir__)
project = Xcodeproj::Project.open(File.join(root, "Farelin.xcodeproj"))
app = project.targets.find { |t| t.name == "Farelin" }
staging = project.main_group.recursive_children.find { |r| r.respond_to?(:path) && r.path == "Staging.xcconfig" }
# Archive staging with Release optimizations and no DEBUG-only test code.
([project] + project.targets).each do |owner|
  release = owner.build_configurations.find { |c| c.name == "Release" }
  configuration = owner.build_configurations.find { |c| c.name == "Staging Release" }
  unless configuration
    configuration = project.new(Xcodeproj::Project::Object::XCBuildConfiguration)
    configuration.name = "Staging Release"
    configuration.build_settings = Marshal.load(Marshal.dump(release.build_settings))
    owner.build_configuration_list.build_configurations << configuration
  end
  configuration.base_configuration_reference = staging
  configuration.build_settings["SWIFT_ACTIVE_COMPILATION_CONDITIONS"] = "$(inherited)"
  configuration.build_settings["GCC_PREPROCESSOR_DEFINITIONS"] = ["$(inherited)"]
  configuration.build_settings["APNS_ENVIRONMENT"] = "production"
  configuration.build_settings["APNS_DELIVERY_ENVIRONMENT"] = "production"
end
project.targets.each do |target|
  target.build_configurations.each do |configuration|
    configuration.build_settings["CODE_SIGN_ENTITLEMENTS"] = target == app ? "Farelin/Resources/Farelin.entitlements" : ""
  end
end
url = "https://github.com/google/GoogleSignIn-iOS"
package = project.root_object.package_references.find { |p| p.repositoryURL == url }
unless package
  package = project.new(Xcodeproj::Project::Object::XCRemoteSwiftPackageReference)
  package.repositoryURL = url
  package.requirement = { "kind" => "exactVersion", "version" => "9.2.0" }
  project.root_object.package_references << package
end
unless app.package_product_dependencies.any? { |d| d.product_name == "GoogleSignIn" }
  product = project.new(Xcodeproj::Project::Object::XCSwiftPackageProductDependency)
  product.package = package
  product.product_name = "GoogleSignIn"
  app.package_product_dependencies << product
  build = project.new(Xcodeproj::Project::Object::PBXBuildFile)
  build.product_ref = product
  app.frameworks_build_phase.files << build
end
%w[Farelin FarelinTests FarelinUITests].each do |name|
  target = project.targets.find { |t| t.name == name }
  group = project.main_group.groups.find { |g| g.path == name }
  next unless target && group
  Dir.glob(File.join(root, name, "**", "*"), File::FNM_DOTMATCH).sort.each do |path|
    next unless File.file?(path) && %w[.swift .xcprivacy].include?(File.extname(path))
    relative = path.delete_prefix(File.join(root, name) + "/")
    next if group.recursive_children.any? { |ref| ref.respond_to?(:real_path) && ref.real_path.to_s == path }
    ref = group.new_file(relative)
    if File.extname(path) == ".swift"
      target.source_build_phase.add_file_reference(ref)
    else
      target.resources_build_phase.add_file_reference(ref)
    end
  end
end
project.save
puts "Synchronized Farelin sources; existing signing settings preserved."
