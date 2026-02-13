import { Client, GatewayIntentBits, EmbedBuilder, AttachmentBuilder, REST, Routes } from 'discord.js';
import dotenv from 'dotenv';
import axios from 'axios';
import EventSource from 'eventsource';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import fs from 'fs';
import { exec } from 'child_process';
import { promisify } from 'util';
import crypto from 'crypto';

const execAsync = promisify(exec);

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Load environment variables from parent directory
dotenv.config({ path: join(__dirname, '..', '.env') });

// Configuration
const DISCORD_BOT_TOKEN = process.env.DISCORD_BOT_TOKEN;
const DISCORD_CLIENT_ID = process.env.DISCORD_CLIENT_ID;
const DISCORD_GUILD_ID = process.env.DISCORD_GUILD_ID;
const API_BASE_URL = process.env.API_BASE_URL || 'http://127.0.0.1:8080';
const API_USERNAME = process.env.API_USERNAME;
const API_PASSWORD = process.env.API_PASSWORD;

// Voice state management
let voiceEnabled = false;
let voiceEventSource = null;
let voiceChannel = null; // Store the channel where voice is active
let pendingVoiceResponses = new Map(); // Track messages waiting for voice

// Conversation state management
let lastActiveChannel = null; // Store the last channel where a message was sent

// Create Discord client
const client = new Client({
    intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMessages,
        GatewayIntentBits.MessageContent,
        GatewayIntentBits.GuildMembers
    ]
});

// Create axios instance with auth
const apiClient = axios.create({
    baseURL: API_BASE_URL,
    auth: {
        username: API_USERNAME,
        password: API_PASSWORD
    },
    timeout: 120000  // Increased to 2 minutes for LLM processing
});

// Helper function to send message to AI
async function sendToAI(message, username) {
    try {
        const formattedMessage = `Message from Discord by ${username}: ${message}`;

        const response = await apiClient.post('/api/chat', {
            message: formattedMessage,
            source: 'discord'  // Indicate this message is from Discord
        });

        return response.data;
    } catch (error) {
        console.error('Error communicating with AI:', error.message);
        throw error;
    }
}

// Helper function to reset notification counter
async function resetNotificationCounter() {
    try {
        await apiClient.post('/api/notifications/user_active');
        await apiClient.post('/api/notifications/reset_waiting');
        console.log('Notification counter reset');
    } catch (error) {
        console.error('Error resetting notification counter:', error.message);
    }
}

// Helper function to check if ffmpeg is available
async function checkFfmpeg() {
    try {
        await execAsync('ffmpeg -version');
        return true;
    } catch (error) {
        return false;
    }
}

// Helper function to convert WAV to OGG Opus
async function convertWavToOgg(wavPath, oggPath) {
    const command = `ffmpeg -hide_banner -y -i "${wavPath}" -c:a libopus -b:a 64k -ar 48000 "${oggPath}"`;
    await execAsync(command);
}

// Helper function to get audio metadata
async function getAudioMetadata(filePath) {
    // Get duration using ffprobe
    const durationCmd = `ffprobe -v error -select_streams a:0 -show_entries format=duration -of json "${filePath}"`;
    const { stdout } = await execAsync(durationCmd);
    const duration = Math.round(parseFloat(JSON.parse(stdout).format.duration));

    // Generate waveform (simplified - just random data like the Python example)
    const waveform = crypto.randomBytes(256).toString('base64');

    return { duration, waveform };
}

// Helper function to download and send voice message as Discord voice message
async function sendVoiceFile(channel, audioUrl) {
    const tempWavPath = join(__dirname, 'temp_voice.wav');
    const tempOggPath = join(__dirname, 'temp_voice.ogg');

    try {
        // Check if ffmpeg is available
        const ffmpegAvailable = await checkFfmpeg();
        if (!ffmpegAvailable) {
            console.error('FFmpeg not found! Please install FFmpeg to enable voice messages.');
            await channel.send('⚠️ Voice message conversion failed: FFmpeg not installed. Please ask the administrator to install FFmpeg.');
            return;
        }

        console.log('Downloading WAV file from AI server...');
        const response = await apiClient.get(audioUrl, {
            responseType: 'arraybuffer'
        });

        // Save WAV file temporarily
        fs.writeFileSync(tempWavPath, Buffer.from(response.data));

        // Convert WAV to OGG Opus
        console.log('Converting WAV to OGG Opus...');
        await convertWavToOgg(tempWavPath, tempOggPath);

        // Get audio metadata
        const { duration, waveform } = await getAudioMetadata(tempOggPath);
        const fileSize = fs.statSync(tempOggPath).size;

        console.log(`Audio metadata: duration=${duration}s, size=${fileSize} bytes`);

        // Step 1: Request upload URL from Discord
        const attachmentResponse = await axios.post(
            `https://discord.com/api/v10/channels/${channel.id}/attachments`,
            {
                files: [{
                    filename: 'voice-message.ogg',
                    file_size: fileSize,
                    id: '0'
                }]
            },
            {
                headers: {
                    'Authorization': `Bot ${DISCORD_BOT_TOKEN}`,
                    'Content-Type': 'application/json'
                }
            }
        );

        const uploadData = attachmentResponse.data.attachments[0];
        const uploadUrl = uploadData.upload_url;
        const uploadedFilename = uploadData.upload_filename;

        // Step 2: Upload OGG file to Discord CDN
        console.log('Uploading to Discord CDN...');
        const oggBuffer = fs.readFileSync(tempOggPath);
        await axios.put(uploadUrl, oggBuffer, {
            headers: {
                'Content-Type': 'audio/ogg'
            }
        });

        // Step 3: Send voice message with proper flags
        console.log('Sending voice message...');
        await axios.post(
            `https://discord.com/api/v10/channels/${channel.id}/messages`,
            {
                flags: 8192,  // IS_VOICE_MESSAGE flag
                attachments: [{
                    id: '0',
                    filename: 'voice-message.ogg',
                    uploaded_filename: uploadedFilename,
                    duration_secs: duration,
                    waveform: waveform
                }]
            },
            {
                headers: {
                    'Authorization': `Bot ${DISCORD_BOT_TOKEN}`,
                    'Content-Type': 'application/json'
                }
            }
        );

        console.log('Voice message sent successfully!');
    } catch (error) {
        console.error('Error sending voice message:', error.response?.data || error.message);
    } finally {
        // Clean up temporary files
        if (fs.existsSync(tempWavPath)) fs.unlinkSync(tempWavPath);
        if (fs.existsSync(tempOggPath)) fs.unlinkSync(tempOggPath);
    }
}

// Setup voice event listener
function setupVoiceListener(channel) {
    if (voiceEventSource) {
        voiceEventSource.close();
    }

    voiceChannel = channel;

    const eventSourceUrl = `${API_BASE_URL}/api/voice/events`;
    voiceEventSource = new EventSource(eventSourceUrl);

    voiceEventSource.onopen = () => {
        console.log('Connected to voice event stream');
    };

    voiceEventSource.onmessage = async (event) => {
        try {
            const data = JSON.parse(event.data);
            console.log('SSE message received:', data);

            if (data.type === 'audio_ready') {
                console.log('Audio ready event detected:', data);

                if (voiceEnabled && data.url && voiceChannel) {
                    console.log('Sending voice file to Discord...');
                    await sendVoiceFile(voiceChannel, data.url);
                } else {
                    console.log('NOT sending voice file. voiceEnabled:', voiceEnabled, 'url:', data.url, 'voiceChannel:', voiceChannel ? 'exists' : 'null');
                }
            } else if (data.type === 'agent_completion') {
                console.log('Agent completion event detected:', data);

                // Send the completion message to Discord
                // Use lastActiveChannel (where conversation is happening) or voiceChannel (if voice is active)
                const targetChannel = lastActiveChannel || voiceChannel;

                if (targetChannel && data.message) {
                    console.log('Sending agent completion message to Discord...');

                    const messageText = data.message;

                    // Discord has a 2000 character limit, split if needed
                    if (messageText.length > 2000) {
                        const chunks = messageText.match(/[\s\S]{1,2000}/g) || [];
                        for (const chunk of chunks) {
                            await targetChannel.send(chunk);
                        }
                    } else {
                        await targetChannel.send(messageText);
                    }
                } else {
                    console.log('NOT sending agent completion. targetChannel:', targetChannel ? 'exists' : 'null', 'message:', data.message ? 'exists' : 'null');
                }
            } else if (data.type === 'voice_notification') {
                console.log('Voice notification:', data);
            } else if (data.type === 'connected') {
                console.log('Connected to voice event stream');
            }
        } catch (error) {
            console.error('Error processing SSE message:', error);
        }
    };

    voiceEventSource.onerror = (error) => {
        console.error('Voice event source error:', error);

        // Only try to reconnect if voice is still enabled
        if (voiceEnabled && voiceChannel) {
            setTimeout(() => {
                console.log('Attempting to reconnect to voice event stream...');
                setupVoiceListener(voiceChannel);
            }, 5000);
        }
    };
}

// Register slash commands
async function registerCommands() {
    const commands = [
        {
            name: 'voice',
            description: 'Manage voice message settings',
            options: [
                {
                    name: 'action',
                    description: 'Action to perform',
                    type: 3, // STRING type
                    required: true,
                    choices: [
                        {
                            name: 'activate',
                            value: 'activate'
                        },
                        {
                            name: 'deactivate',
                            value: 'deactivate'
                        },
                        {
                            name: 'status',
                            value: 'status'
                        }
                    ]
                }
            ]
        },
        {
            name: 'llm',
            description: 'Manage LLM provider settings',
            options: [
                {
                    name: 'action',
                    description: 'Action to perform',
                    type: 3, // STRING type
                    required: true,
                    choices: [
                        {
                            name: 'change',
                            value: 'change'
                        },
                        {
                            name: 'status',
                            value: 'status'
                        }
                    ]
                },
                {
                    name: 'provider',
                    description: 'LLM provider to use (for change action)',
                    type: 3, // STRING type
                    required: false,
                    choices: [
                        {
                            name: 'ollama',
                            value: 'ollama'
                        },
                        {
                            name: 'gemini',
                            value: 'gemini'
                        },
                        {
                            name: 'openrouter',
                            value: 'openrouter'
                        }
                    ]
                }
            ]
        }
    ];

    try {
        const rest = new REST({ version: '10' }).setToken(DISCORD_BOT_TOKEN);

        if (DISCORD_GUILD_ID) {
            // Register guild-specific commands (instant update)
            await rest.put(
                Routes.applicationGuildCommands(DISCORD_CLIENT_ID, DISCORD_GUILD_ID),
                { body: commands }
            );
            console.log('Successfully registered guild-specific slash commands');
        } else {
            // Register global commands (takes up to 1 hour to propagate)
            await rest.put(
                Routes.applicationCommands(DISCORD_CLIENT_ID),
                { body: commands }
            );
            console.log('Successfully registered global slash commands');
        }
    } catch (error) {
        console.error('Error registering slash commands:', error);
    }
}

// Handle slash commands
client.on('interactionCreate', async interaction => {
    if (!interaction.isChatInputCommand()) return;

    if (interaction.commandName === 'voice') {
        const action = interaction.options.getString('action');

        try {
            if (action === 'activate') {
                // Defer reply immediately since starting voice takes time
                await interaction.deferReply();

                // Start voice system with longer timeout
                await apiClient.post('/api/voice/start', {}, { timeout: 120000 });
                voiceEnabled = true;

                // Update voice channel (SSE connection already exists from bot startup)
                voiceChannel = interaction.channel;

                const embed = new EmbedBuilder()
                    .setColor(0x00FF00)
                    .setTitle('Voice Activated')
                    .setDescription('Voice messages are now enabled. I will send audio responses to this channel.')
                    .setTimestamp();

                await interaction.editReply({ embeds: [embed] });

            } else if (action === 'deactivate') {
                voiceEnabled = false;
                voiceChannel = null;

                // Don't close the SSE connection - we still need it for agent completions
                // The connection will remain active but voice audio won't be sent

                const embed = new EmbedBuilder()
                    .setColor(0xFF0000)
                    .setTitle('Voice Deactivated')
                    .setDescription('Voice messages are now disabled. Agent completion messages will still appear.')
                    .setTimestamp();

                await interaction.reply({ embeds: [embed] });

            } else if (action === 'status') {
                const voiceStatus = await apiClient.get('/api/voice/status');

                const embed = new EmbedBuilder()
                    .setColor(voiceEnabled ? 0x00FF00 : 0xFF0000)
                    .setTitle('Voice Status')
                    .addFields(
                        { name: 'Discord Voice', value: voiceEnabled ? 'Enabled' : 'Disabled', inline: true },
                        { name: 'xVAsynth Server', value: voiceStatus.data.initialized ? 'Running' : 'Stopped', inline: true }
                    )
                    .setTimestamp();

                await interaction.reply({ embeds: [embed] });
            }
        } catch (error) {
            console.error('Error handling voice command:', error);

            // Try to send error message
            try {
                if (interaction.deferred) {
                    await interaction.editReply({ content: 'Error executing voice command. Check if the AI server is running.' });
                } else if (!interaction.replied) {
                    await interaction.reply({ content: 'Error executing voice command. Check if the AI server is running.', flags: 64 });
                }
            } catch (replyError) {
                console.error('Could not send error reply:', replyError.message);
            }
        }
    } else if (interaction.commandName === 'llm') {
        const action = interaction.options.getString('action');
        const provider = interaction.options.getString('provider');

        try {
            if (action === 'change') {
                if (!provider) {
                    await interaction.reply({
                        content: 'Please specify a provider: ollama, gemini, or openrouter',
                        flags: 64
                    });
                    return;
                }

                // Change the LLM provider via API
                await apiClient.post('/api/settings/provider', { provider });

                const embed = new EmbedBuilder()
                    .setColor(0x00FF00)
                    .setTitle('LLM Provider Changed')
                    .setDescription(`LLM provider switched to **${provider}**`)
                    .setTimestamp();

                await interaction.reply({ embeds: [embed] });

            } else if (action === 'status') {
                // Get current provider status
                const response = await apiClient.get('/api/settings/provider');
                const currentProvider = response.data.provider;
                const currentModel = response.data.model;

                const embed = new EmbedBuilder()
                    .setColor(0x3498db)
                    .setTitle('LLM Provider Status')
                    .addFields(
                        { name: 'Current Provider', value: currentProvider, inline: true },
                        { name: 'Current Model', value: currentModel, inline: true }
                    )
                    .setTimestamp();

                await interaction.reply({ embeds: [embed] });
            }
        } catch (error) {
            console.error('Error handling llm command:', error);

            // Try to send error message
            try {
                if (interaction.deferred) {
                    await interaction.editReply({ content: 'Error executing llm command. Check if the AI server is running.' });
                } else if (!interaction.replied) {
                    await interaction.reply({ content: 'Error executing llm command. Check if the AI server is running.', flags: 64 });
                }
            } catch (replyError) {
                console.error('Could not send error reply:', replyError.message);
            }
        }
    }
});

// Handle messages
client.on('messageCreate', async message => {
    // Ignore bot messages
    if (message.author.bot) return;

    // Only respond to messages that mention the bot or are DMs
    const isMentioned = message.mentions.has(client.user);
    const isDM = message.channel.type === 1; // DM channel type

    if (!isMentioned && !isDM) return;

    try {
        // Track the active channel for agent completions and other events
        lastActiveChannel = message.channel;

        // Show typing indicator
        await message.channel.sendTyping();

        // Reset notification counter when user interacts
        await resetNotificationCounter();

        // Get username
        const username = message.author.username;

        // Extract message content (remove bot mention if present)
        let messageContent = message.content;
        if (isMentioned) {
            messageContent = messageContent.replace(/<@!?\d+>/g, '').trim();
        }

        // Send to AI
        const aiResponse = await sendToAI(messageContent, username);

        // Only send text response if voice is NOT enabled
        // When voice is enabled, we wait for the audio file instead
        if (!voiceEnabled && aiResponse.response) {
            // Discord has a 2000 character limit, split if needed
            const responseText = aiResponse.response;
            if (responseText.length > 2000) {
                const chunks = responseText.match(/[\s\S]{1,2000}/g) || [];
                for (const chunk of chunks) {
                    await message.reply(chunk);
                }
            } else {
                await message.reply(responseText);
            }
        } else if (voiceEnabled) {
            // Voice is enabled - audio will be sent via event listener
            // Optionally send a typing indicator or "processing" message
            console.log('Waiting for voice synthesis to complete...');
        }

    } catch (error) {
        console.error('Error processing message:', error);
        await message.reply('Sorry, I encountered an error processing your message. Make sure the AI server is running.');
    }
});

// Bot ready event
client.on('ready', async () => {
    console.log(`Logged in as ${client.user.tag}`);
    console.log(`Bot is ready and connected to Discord!`);

    // Check for ffmpeg
    const ffmpegAvailable = await checkFfmpeg();
    if (ffmpegAvailable) {
        console.log('✓ FFmpeg is available');
    } else {
        console.warn('⚠ FFmpeg not found - voice messages will not work!');
    }

    // Register slash commands
    await registerCommands();

    // Set bot status
    client.user.setActivity('for mentions | /voice /llm', { type: 3 }); // Type 3 = WATCHING

    // Notify monitoring service that Discord bot is active
    try {
        await apiClient.post('/api/monitoring/discord_status', { active: true });
        console.log('✓ Registered with monitoring service');
    } catch (error) {
        console.warn('⚠ Could not register with monitoring service:', error.message);
    }

    // Initialize SSE connection for agent completions and voice events
    // This runs independently of voice activation
    console.log('Connecting to event stream for agent completions...');
    setupVoiceListener(null); // Pass null since we don't have a channel yet
});

// Error handling
client.on('error', error => {
    console.error('Discord client error:', error);
});

process.on('unhandledRejection', error => {
    console.error('Unhandled promise rejection:', error);
});

// Login to Discord
if (!DISCORD_BOT_TOKEN) {
    console.error('ERROR: DISCORD_BOT_TOKEN not found in .env file');
    process.exit(1);
}

if (!DISCORD_CLIENT_ID) {
    console.error('ERROR: DISCORD_CLIENT_ID not found in .env file');
    process.exit(1);
}

client.login(DISCORD_BOT_TOKEN);
