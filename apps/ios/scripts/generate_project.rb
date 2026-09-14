#!/usr/bin/env ruby

require "fileutils"
require "xcodeproj"

ROOT = File.expand_path("..", __dir__)
PROJECT_PATH = File.join(ROOT, "Farelin.xcodeproj")

FileUtils.rm_rf(PROJECT_PATH)
project = Xcodeproj::Project.new(PROJECT_PATH)
project.root_object.attributes["LastSwiftUpdateCheck"] = "2660"
project.root_object.attributes["LastUpgradeCheck"] = "2660"

config_group = project.main_group.new_group("Config", "Config")
staging_config = config_group.new_file("Staging.xcconfig")
production_config = config_group.new_file("Production.xcconfig")
config_group.new_file("Base.xcconfig")

app_group = project.main_group.new_group("Farelin", "Farelin")
test_group = project.main_group.new_group("FarelinTests", "FarelinTests")
ui_test_group = project.main_group.new_group("FarelinUITests", "FarelinUITests")

app = project.new_target(:application, "Farelin", :ios, "17.0")
tests = project.new_target(:unit_test_bundle, "FarelinTests", :ios, "17.0")
ui_tests = project.new_target(:ui_test_bundle, "FarelinUITests", :ios, "17.0")

def add_tree(group, target, root, relative_path)
  absolute_path = File.join(root, relative_path)
  Dir.children(absolute_path).sort.each do |entry|
    child_relative = File.join(relative_path, entry)
    child_absolute = File.join(root, child_relative)
    if File.directory?(child_absolute) && !entry.end_with?(".xcassets")
      child_group = group.new_group(entry, entry)
      add_tree(child_group, target, root, child_relative)
      next
    end

    reference = group.new_file(entry)
    case File.extname(entry)
    when ".swift"
      target.source_build_phase.add_file_reference(reference)
    when ".xcassets"
      target.resources_build_phase.add_file_reference(reference)
    end
  end
end

add_tree(app_group, app, ROOT, "Farelin")
add_tree(test_group, tests, ROOT, "FarelinTests")
add_tree(ui_test_group, ui_tests, ROOT, "FarelinUITests")

project.build_configurations.each do |configuration|
  configuration.base_configuration_reference = configuration.name == "Debug" ? staging_config : production_config
  configuration.build_settings["IPHONEOS_DEPLOYMENT_TARGET"] = "17.0"
end

[app, tests, ui_tests].each do |target|
  target.build_configurations.each do |configuration|
    configuration.base_configuration_reference = configuration.name == "Debug" ? staging_config : production_config
    configuration.build_settings.delete("PRODUCT_BUNDLE_IDENTIFIER")
    configuration.build_settings["SWIFT_VERSION"] = "6.0"
    configuration.build_settings["SWIFT_STRICT_CONCURRENCY"] = "complete"
    configuration.build_settings["TARGETED_DEVICE_FAMILY"] = "1"
  end
end

app.build_configurations.each do |configuration|
  configuration.build_settings["ASSETCATALOG_COMPILER_APPICON_NAME"] = "AppIcon"
  configuration.build_settings["PRODUCT_NAME"] = "Farelin"
end

tests.add_dependency(app)
tests.build_configurations.each do |configuration|
  configuration.build_settings["PRODUCT_BUNDLE_IDENTIFIER"] = "com.farelin.tests"
  configuration.build_settings["GENERATE_INFOPLIST_FILE"] = "YES"
  configuration.build_settings["INFOPLIST_FILE"] = ""
  configuration.build_settings["TEST_HOST"] = "$(BUILT_PRODUCTS_DIR)/Farelin.app/$(BUNDLE_EXECUTABLE_FOLDER_PATH)/Farelin"
  configuration.build_settings["BUNDLE_LOADER"] = "$(TEST_HOST)"
end

ui_tests.add_dependency(app)
ui_tests.build_configurations.each do |configuration|
  configuration.build_settings["PRODUCT_BUNDLE_IDENTIFIER"] = "com.farelin.uitests"
  configuration.build_settings["GENERATE_INFOPLIST_FILE"] = "YES"
  configuration.build_settings["INFOPLIST_FILE"] = ""
  configuration.build_settings["TEST_TARGET_NAME"] = "Farelin"
end

def make_scheme(project, name, app, tests, ui_tests, configuration:, include_tests:)
  scheme = Xcodeproj::XCScheme.new
  scheme.add_build_target(app)
  if include_tests
    scheme.add_build_target(tests)
    scheme.add_build_target(ui_tests)
    scheme.add_test_target(tests)
    scheme.add_test_target(ui_tests)
  end
  scheme.launch_action.build_configuration = configuration
  scheme.profile_action.build_configuration = configuration
  scheme.analyze_action.build_configuration = configuration
  scheme.archive_action.build_configuration = configuration
  scheme.test_action.build_configuration = configuration == "Release" ? "Debug" : configuration
  scheme.set_launch_target(app)
  scheme.save_as(project.path, name, true)
end

make_scheme(project, "Farelin Staging", app, tests, ui_tests, configuration: "Debug", include_tests: true)
make_scheme(project, "Farelin", app, tests, ui_tests, configuration: "Release", include_tests: false)

project.save
puts "Generated #{PROJECT_PATH}"
