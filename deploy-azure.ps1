<#
.SYNOPSIS
  Deploy MarketMind to Azure: PostgreSQL Flexible Server, a container registry,
  and two containers (FastAPI backend, nginx + React frontend) on Container Apps
  or App Service.

.DESCRIPTION
  Safe to re-run: existing resources are reused, and new images are built,
  pushed and rolled out. Settings come from .env (Azure OpenAI endpoint, key and
  deployment); secrets are stored as Container Apps secrets or App Service app
  settings, never in images. Images are built with the local Docker engine and
  pushed to the registry.

  -Hosting appservice runs both containers on one Linux App Service plan, for
  subscriptions (such as sandboxes) that don't allow Container Apps.

.EXAMPLE
  ./deploy-azure.ps1                          # first deploy, or update
  ./deploy-azure.ps1 -Location westeurope     # choose a region on first deploy
  ./deploy-azure.ps1 -Hosting appservice -ResourceGroup my-sandbox-rg
  az group delete -n marketmind-rg            # remove everything
#>
param(
    [string]$ResourceGroup = "marketmind-rg",
    [string]$Location = "eastus",
    [string]$Prefix = "marketmind",
    [string]$Tag = (Get-Date -Format "yyyyMMddHHmm"),
    [ValidateSet("containerapps", "appservice")]
    [string]$Hosting = "containerapps",
    [string]$AppServiceSku = "B2"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Native tools (az, docker) report failure through exit codes. Their stderr carries
# progress and warnings, which Windows PowerShell 5.1 would turn into errors under
# "Stop", so these helpers run them under "Continue" and check the exit code.
function Invoke-Az {
    $ErrorActionPreference = "Continue"
    $out = & az @args --only-show-errors
    if ($LASTEXITCODE -ne 0) { throw "az $($args[0..2] -join ' ') failed (exit $LASTEXITCODE)" }
    return $out
}

function Test-Az {
    # True when an az "show" call succeeds (the resource exists).
    $ErrorActionPreference = "Continue"
    & az @args --only-show-errors 2>$null | Out-Null
    return $LASTEXITCODE -eq 0
}

function Invoke-Docker {
    $ErrorActionPreference = "Continue"
    & docker @args
    if ($LASTEXITCODE -ne 0) { throw "docker $($args[0]) failed (exit $LASTEXITCODE)" }
}

function Read-DotEnv([string]$Path) {
    $values = @{}
    foreach ($line in Get-Content $Path) {
        if ($line -match '^\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$') {
            $values[$Matches[1]] = $Matches[2].Trim('"').Trim("'")
        }
    }
    return $values
}

if (-not (Test-Path .env)) { throw ".env not found: copy .env.example and fill in the Azure OpenAI settings." }
$envFile = Read-DotEnv .env
foreach ($name in "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_CHAT_DEPLOYMENT") {
    if (-not $envFile[$name]) { throw "$name is empty in .env" }
}

# Names derived from the subscription, so re-runs find the same resources.
$subscription = Invoke-Az account show --query id -o tsv
$suffix = $subscription.Substring(0, 6)
$acr = "$($Prefix)acr$suffix" -replace '[^a-z0-9]', ''
$pg = "$Prefix-pg-$suffix"
$caEnv = "$Prefix-env"
$api = "$Prefix-api"
$web = "$Prefix-web"
# App Service names are global host names (<name>.azurewebsites.net), so they carry the suffix.
$plan = "$Prefix-plan"
$apiSite = "$Prefix-api-$suffix"
$webSite = "$Prefix-web-$suffix"
$db = "knowledge_assistant"
$pgUser = "mmadmin"

Write-Host "==> Subscription $subscription, resource group $ResourceGroup, hosting $Hosting"
$providers = @("Microsoft.DBforPostgreSQL", "Microsoft.ContainerRegistry")
if ($Hosting -eq "containerapps") {
    Invoke-Az extension add --name containerapp --upgrade | Out-Null
    $providers += "Microsoft.App", "Microsoft.OperationalInsights"
} else {
    $providers += "Microsoft.Web"
}
foreach ($provider in $providers) {
    # Registering needs subscription-level rights, which sandbox accounts often lack; skip it when already done.
    if ((Invoke-Az provider show -n $provider --query registrationState -o tsv) -ne "Registered") {
        Invoke-Az provider register -n $provider --wait | Out-Null
    }
}

if (-not (Test-Az group show -n $ResourceGroup)) {
    Invoke-Az group create -n $ResourceGroup -l $Location -o none
}
$Location = Invoke-Az group show -n $ResourceGroup --query location -o tsv

# --- Container registry and images --------------------------------------------
if (-not (Test-Az acr show -n $acr -g $ResourceGroup)) {
    Write-Host "==> Creating container registry $acr"
    Invoke-Az acr create -g $ResourceGroup -n $acr --sku Basic -o none
}
$registry = Invoke-Az acr show -n $acr --query loginServer -o tsv
Invoke-Az acr login -n $acr | Out-Null

Write-Host "==> Building and pushing images (tag $Tag)"
Invoke-Docker build -t "$registry/$($api):$Tag" .
Invoke-Docker build -t "$registry/$($web):$Tag" ./frontend-react
Invoke-Docker push "$registry/$($api):$Tag"
Invoke-Docker push "$registry/$($web):$Tag"

# --- PostgreSQL -------------------------------------------------------------------
function New-PgPassword {
    $chars = [char[]]"ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"
    return "Mm9-" + (-join (1..24 | ForEach-Object { $chars | Get-Random }))
}

function Get-StoredDbUrl {
    # The connection string saved with the backend on an earlier run, if there is one.
    if ($Hosting -eq "containerapps") {
        if (Test-Az containerapp show -g $ResourceGroup -n $api) {
            return Invoke-Az containerapp secret show -g $ResourceGroup -n $api --secret-name db-url --query value -o tsv
        }
    } elseif (Test-Az webapp show -g $ResourceGroup -n $apiSite) {
        return Invoke-Az webapp config appsettings list -g $ResourceGroup -n $apiSite --query "[?name=='DATABASE_URL'].value | [0]" -o tsv
    }
    return $null
}

$dbUrl = $null
$pgPassword = $null
if (-not (Test-Az postgres flexible-server show -g $ResourceGroup -n $pg)) {
    Write-Host "==> Creating PostgreSQL server $pg (takes 5-10 minutes)"
    $pgPassword = New-PgPassword
    Invoke-Az postgres flexible-server create -g $ResourceGroup -n $pg -l $Location `
        --tier Burstable --sku-name Standard_B1ms --version 16 --storage-size 32 `
        --admin-user $pgUser --admin-password $pgPassword --public-access 0.0.0.0 `
        --yes -o none
} elseif ($dbUrl = Get-StoredDbUrl) {
    # Re-run: reuse the connection string stored with the backend.
} else {
    # The server exists but its password was never stored (an earlier run stopped part-way): set a new one.
    Write-Host "==> Resetting the admin password of PostgreSQL server $pg"
    $pgPassword = New-PgPassword
    Invoke-Az postgres flexible-server update -g $ResourceGroup -n $pg --admin-password $pgPassword -o none
}
if ($pgPassword) {
    if (-not (Test-Az postgres flexible-server db show -g $ResourceGroup --server-name $pg --name $db)) {
        Invoke-Az postgres flexible-server db create -g $ResourceGroup --server-name $pg --name $db -o none
    }
    $dbUrl = "postgresql+psycopg://$($pgUser):$pgPassword@$pg.postgres.database.azure.com:5432/$($db)?sslmode=require"
}

$common = @(
    "AZURE_OPENAI_ENDPOINT=$($envFile['AZURE_OPENAI_ENDPOINT'])",
    "AZURE_OPENAI_CHAT_DEPLOYMENT=$($envFile['AZURE_OPENAI_CHAT_DEPLOYMENT'])",
    "EMBEDDING_PROVIDER=fastembed",
    "LOG_LEVEL=INFO"
)
foreach ($name in "AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "LLM_PROVIDER", "AGENT_TIMEOUT", "FASTEMBED_MODEL", "RETRIEVAL_MIN_SCORE") {
    if ($envFile[$name]) { $common += "$name=$($envFile[$name])" }
}

# --- App Service ------------------------------------------------------------------
if ($Hosting -eq "appservice") {
    if (-not (Test-Az appservice plan show -g $ResourceGroup -n $plan)) {
        Write-Host "==> Creating App Service plan $plan ($AppServiceSku, Linux)"
        Invoke-Az appservice plan create -g $ResourceGroup -n $plan -l $Location --is-linux --sku $AppServiceSku -o none
    }
    $acrId = Invoke-Az acr show -n $acr --query id -o tsv

    function Set-Site([string]$Name, [string]$Image, [string[]]$Settings) {
        if (-not (Test-Az webapp show -g $ResourceGroup -n $Name)) {
            Write-Host "==> Creating web app $Name"
            # The app's managed identity pulls from the registry (AcrPull); no registry passwords.
            Invoke-Az webapp create -g $ResourceGroup -p $plan -n $Name --container-image-name $Image `
                --assign-identity "[system]" --role AcrPull --scope $acrId --acr-use-identity -o none
        } else {
            Write-Host "==> Updating web app $Name"
        }
        Invoke-Az webapp config appsettings set -g $ResourceGroup -n $Name --settings @Settings -o none
        Invoke-Az webapp config set -g $ResourceGroup -n $Name --always-on true --http20-enabled true -o none
        Invoke-Az webapp update -g $ResourceGroup -n $Name --https-only true -o none
        Invoke-Az webapp config container set -g $ResourceGroup -n $Name --container-image-name $Image `
            --container-registry-url "https://$registry" -o none
        Invoke-Az webapp restart -g $ResourceGroup -n $Name -o none
    }

    $apiSettings = $common + @(
        "DATABASE_URL=$dbUrl",
        "AZURE_OPENAI_API_KEY=$($envFile['AZURE_OPENAI_API_KEY'])",
        "WEBSITES_PORT=8000",
        "WEBSITES_CONTAINER_START_TIME_LIMIT=900"  # first start builds the search index
    )
    Set-Site $apiSite "$registry/$($api):$Tag" $apiSettings
    $apiHost = Invoke-Az webapp show -g $ResourceGroup -n $apiSite --query defaultHostName -o tsv
    Set-Site $webSite "$registry/$($web):$Tag" @("BACKEND_URL=https://$apiHost", "WEBSITES_PORT=80")

    $url = "https://" + (Invoke-Az webapp show -g $ResourceGroup -n $webSite --query defaultHostName -o tsv)
    Write-Host ""
    Write-Host "MarketMind is deployed: $url"
    Write-Host "The backend needs a few minutes on first start to pull its image and build its search index."
    Write-Host "Note: App Service ends requests after 230 seconds, so very long AI analyses can time out."
    Write-Host "Add a sign-in: Azure portal > $webSite > Authentication > Add identity provider > Microsoft."
    return
}

# --- Container Apps -------------------------------------------------------------
if (-not (Test-Az containerapp env show -g $ResourceGroup -n $caEnv)) {
    Write-Host "==> Creating Container Apps environment $caEnv"
    Invoke-Az containerapp env create -g $ResourceGroup -n $caEnv -l $Location -o none
}

$secrets = @("db-url=$dbUrl", "aoai-key=$($envFile['AZURE_OPENAI_API_KEY'])")
$settings = @(
    "DATABASE_URL=secretref:db-url",
    "AZURE_OPENAI_API_KEY=secretref:aoai-key"
) + $common

if (-not (Test-Az containerapp show -g $ResourceGroup -n $api)) {
    Write-Host "==> Creating backend app $api"
    Invoke-Az containerapp create -g $ResourceGroup -n $api --environment $caEnv `
        --image "$registry/$($api):$Tag" --registry-server $registry --registry-identity system `
        --target-port 8000 --ingress internal --cpu 1 --memory 2Gi --min-replicas 1 --max-replicas 1 `
        --secrets @secrets --env-vars @settings -o none
} else {
    Write-Host "==> Updating backend app $api"
    Invoke-Az containerapp secret set -g $ResourceGroup -n $api --secrets @secrets -o none
    Invoke-Az containerapp update -g $ResourceGroup -n $api --image "$registry/$($api):$Tag" --set-env-vars @settings -o none
}

if (-not (Test-Az containerapp show -g $ResourceGroup -n $web)) {
    Write-Host "==> Creating frontend app $web"
    Invoke-Az containerapp create -g $ResourceGroup -n $web --environment $caEnv `
        --image "$registry/$($web):$Tag" --registry-server $registry --registry-identity system `
        --target-port 80 --ingress external --cpu 0.25 --memory 0.5Gi --min-replicas 1 --max-replicas 2 `
        --env-vars "BACKEND_URL=http://$api" -o none
} else {
    Write-Host "==> Updating frontend app $web"
    Invoke-Az containerapp update -g $ResourceGroup -n $web --image "$registry/$($web):$Tag" -o none
}

$url = "https://" + (Invoke-Az containerapp show -g $ResourceGroup -n $web --query properties.configuration.ingress.fqdn -o tsv)
Write-Host ""
Write-Host "MarketMind is deployed: $url"
Write-Host "The backend needs a minute or two on first start to build its search index."
Write-Host "Add a sign-in: Azure portal > $web > Authentication > Add identity provider > Microsoft."
