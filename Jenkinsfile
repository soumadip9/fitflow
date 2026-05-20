pipeline {
    agent any

    environment {
        // Matches the ID of the credentials we added in Jenkins
        DOCKERHUB_CREDENTIALS = credentials('dockerhub-token')
        DOCKER_IMAGE = "soumadipghosh/fitflow"
    }

    stages {
        stage('Checkout') {
            steps {
                // Pulls the latest code from your GitHub main branch
                checkout scm
            }
        }
        
        stage('Build Docker Image') {
            steps {
                script {
                    echo "Building Docker Image..."
                    // Uses 'bat' instead of 'sh' for Windows Jenkins
                    bat "docker build -t ${DOCKER_IMAGE}:latest ."
                }
            }
        }
        
        stage('Push to Docker Hub') {
            steps {
                script {
                    echo "Logging into Docker Hub..."
                    bat "echo %DOCKERHUB_CREDENTIALS_PSW% | docker login -u %DOCKERHUB_CREDENTIALS_USR% --password-stdin"
                    
                    echo "Pushing Image to Docker Hub..."
                    bat "docker push ${DOCKER_IMAGE}:latest"
                }
            }
        }
    }
}
