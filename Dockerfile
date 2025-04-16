# Use Python 3.11  base image
FROM python:3.11

# Set working directory
WORKDIR /app

# Copy the rest of the application
COPY . .

# Update the package list and install necessary packages  
RUN apt-get update && \  
    apt-get install -y \  
    curl \  
    apt-transport-https \  
    gnupg2 \  
    libodbc2 \
    build-essential \  
    ca-certificates \ 
    && rm -rf /var/lib/apt/lists/*  

# Add the Microsoft repository key  
RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add -  
  
# Add the Microsoft repository  
RUN curl https://packages.microsoft.com/config/ubuntu/20.04/prod.list > /etc/apt/sources.list.d/mssql-release.list  
  
# Update the package list again  
RUN apt-get update  
  
# Install the msodbcsql17 driver and dependencies  
RUN ACCEPT_EULA=Y apt-get install -y msodbcsql17  
  
# Install optional: UnixODBC development headers  
RUN apt-get install -y unixodbc-dev  
  
# Clean up  
RUN apt-get clean && \  
    rm -rf /var/lib/apt/lists/*  

# Copy the root certificate into the container using JSON array format
COPY Sectigo_Public_Server_Authentication_Root_R46.crt /etc/ssl/certs/.
 
# Update the certificate store
RUN update-ca-certificates
 
# Set the CURL_CA_BUNDLE environment variable
ENV CURL_CA_BUNDLE=/etc/ssl/certs/Sectigo_Public_Server_Authentication_Root_R46.crt

# Set the REQUESTS_CA_BUNDLE environment variable
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port the app runs on
EXPOSE 8000

# Start the application with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--timeout", "120", "app:app"]