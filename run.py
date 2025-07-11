"""
My Inner Scope - Self-Reflection Web Application
Copyright 2025 Peremil Starklint Söderström

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import os
from typing import NoReturn

from app import create_app

if __name__ == "__main__":
    # Create the app
    app = create_app()

    # Get port from environment variable or default to 5000
    port = int(os.environ.get("PORT", 5000))

    # Run the app
    app.run(host="0.0.0.0", port=port, debug=app.config["DEBUG"])
