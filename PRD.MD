# Product Requirements Document: Simplified Access Manager

## 1. Introduction

### 1.1. Vision
To create an incredibly simple, fast, and reliable desktop application for managing employee access permissions to various company systems. This tool will replace manual, error-prone processes with a clear, streamlined digital workflow, focusing on core functionalities: managing the access matrix, and generating standardized PDF forms for new hires and departures.

### 1.2. Goals
- **Simplify Access Management**: Drastically reduce the time and complexity required for IT and HR to assign and revoke system access.
- **Enhance Security & Compliance**: Ensure that access rights are clearly defined, consistently applied, and properly documented through standardized forms.
- **Eliminate Redundancy**: Provide a single source of truth for department structures, roles, and their corresponding system permissions.
- **Prioritize Simplicity**: Build a minimal, intuitive application that is easy to learn and operate without extensive training.

### 1.3. User Personas
- **IT Administrator (Primary User)**: Responsible for setting up and managing the access matrix, generating forms upon request, and ensuring data accuracy. Needs a tool that is fast, straightforward, and reliable.
- **HR Manager (Secondary User)**: Initiates access requests for new employees and requests access removal for departing employees. Needs visibility into what access a specific role receives.
- **Department Manager (Viewer)**: Needs to view and confirm the standard access permissions for roles within their department.

## 2. Functional Requirements

### 2.1. Core Features

#### Access Matrix Management
- The main screen will display a matrix with Positions (grouped by Department) as rows and Systems (grouped by Category) as columns.
- IT Admins can click a checkbox at the intersection of a position and a system to grant or revoke that permission.
- Changes to the matrix are saved automatically to a simple local file (e.g., JSON or SQLite).

#### Data Management (CRUD Operations)
- **Departments & Positions**: Ability to add, rename, and delete departments and the positions within them.
- **Systems & Categories**: Ability to add, rename, and delete system categories and the individual systems within them.

#### Form Generation
- A dedicated "Form Generator" section where the user can select an employee's position.
- **New Hire Form**: Based on the selected position, the application generates two PDF documents:
  - **Access Request Form**: A form pre-filled with employee details and checkboxes marked for all systems they are granted access to.
  - **IT Checklist Form**: A simplified checklist showing only the systems the employee should have access to, for internal IT use.
- **Departure Form**: A simple, standardized PDF checklist to track the removal of all company assets and system access for a departing employee.
- Generated forms are saved to a local generated-forms directory, organized into folders by employee name.

#### User Authentication
- A basic login screen to differentiate between an admin (can edit everything) and a viewer (read-only access).
- Passwords will be securely hashed.

### 2.2. User Interface and Experience
- **Simplicity is Key**: The UI will be clean, uncluttered, and built with standard UI components. No complex menus or hidden features.
- **Single-Window Interface**: All functionalities (Matrix, Data Management, Form Generator) will be accessible through clear tabs or sections within a single main window.
- **Intuitive Navigation**: Users should be able to understand and operate the application with minimal guidance.

## 3. Non-Functional Requirements
- **Performance**: The application must launch quickly and respond instantly to user input. Data loading and form generation should be near-instantaneous.
- **Reliability**: The application must be stable and operate without crashes. Data integrity is paramount.
- **Maintainability**: The codebase must be simple, well-documented, and easy for a developer to understand and modify.
- **Platform**: The application will be a standalone desktop application for Windows.

## 4. Wireframes (Conceptual Description)

### Login Screen
A single centered box with fields for "Username," "Password," and a "Login" button.

### Main Application Window
A simple tabbed interface at the top: "Access Matrix", "Manage Data", "Generate Forms".

#### Access Matrix Tab
A large table/grid. Departments and positions are listed down the left side. System categories and systems are listed across the top. The body of the grid contains checkboxes.

#### Manage Data Tab
Simple two-column layouts. The left column lists items (e.g., Departments), and the right column shows details or sub-items (e.g., Positions in that department). "Add," "Rename," and "Delete" buttons are clearly visible.

#### Generate Forms Tab
A simple form with a dropdown to select the "Department" and then the "Position." A text field for "Employee Name" is provided. Buttons are present to "Generate New Hire Forms" and "Generate Departure Form."